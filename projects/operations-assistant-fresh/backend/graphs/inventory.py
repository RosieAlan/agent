from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode

from core.model import model
from tools import check_inventory
from typing import Literal  # 将分类值限定在指定字符串中。

from pydantic import BaseModel, Field
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.types import interrupt  # 暂停图，等待调用方提交选择。
import json

from services.answer_review import review_inventory_answer, refine_inventory_answer

# 绑定工具：让模型获得库存工具的说明和参数格式。
inventory_model = model.bind_tools([check_inventory])


class InventoryState(MessagesState):
    """本次流程共享的消息、模型轮数和请求类别。"""

    model_rounds: int
    intent: Literal["inventory", "chat"]  # 新增：分类结果。
    review_passed: bool  # 最后一次评审是否通过。
    review_issues: list[str]  # 最后一次评审提出的具体问题。
    revise_count: int  # 已完成的修订次数。
    require_confirmation: bool  # 本次请求是否要求执行前确认。
    approved: bool  # 用户选择；由后端确认节点写入。


def confirm_request(state: InventoryState) -> dict:
    """执行前确认整个请求；恢复时本函数会从头执行。"""
    if not state.get("require_confirmation", False):
        return {"approved": True}  # 沿用原有直接查询行为。

    user_input = next(
        message.content for message in reversed(state["messages"])
        if isinstance(message, HumanMessage)
    )
    approved = interrupt({
        "question": "是否继续执行本次库存助手请求？",
        "input": user_input,  # 展示原始问题，确认范围与实际任务保持一致。
        "scope": "只读查询与分析，不修改库存、不发送通知",
    })
    if type(approved) is not bool:
        raise RuntimeError("确认结果必须是布尔值")
    return {"approved": approved}


def route_confirmation(state: InventoryState) -> str:
    return "classifier" if state["approved"] else "cancelled"


def cancel_request(state: InventoryState) -> dict:
    return {
        "messages": [AIMessage(content="已取消本次请求，未执行库存查询与模型分析。")],
    }  # 直接生成取消结果；本路径无模型调用和工具执行。


class IntentResult(BaseModel):
    """约束模型返回的分类格式。"""

    intent: Literal["inventory", "chat"] = Field(
        description="库存查询或检查为inventory，问候及能力咨询为chat",
    )


# 创建结构化分类模型；执行ainvoke时才会请求模型。
classifier_model = model.with_structured_output(IntentResult)


async def classify_request(state: InventoryState) -> dict:
    """读取用户问题，将分类结果写进State。"""

    user_message = state["messages"][-1]  # 当前入口传入的最后一条是用户问题。

    result = await classifier_model.ainvoke(
        [
            SystemMessage(
                content=(
                    "将用户请求分为inventory或chat。"
                    "inventory：查询库存数量、检查低库存、询问商品是否缺货。"
                    "即使缺少商品编号，只要目的涉及库存，也归inventory。"
                    "chat：问候、感谢、咨询助手能力及其他当前不支持的话题。"
                    "例如：'检查耳机库存'为inventory；'你好'为chat。"
                )
            ),
            user_message,
        ]
    )

    return {"intent": result.intent}  # 仅更新分类字段，已有消息继续保留。


def route_request(state: InventoryState) -> str:
    """读取分类结果，选择后续节点。"""

    if state["intent"] == "inventory":
        return "agent"  # 进入已有库存工具循环。

    return "chat"  # 进入直接回答步骤。


async def reply_chat(state: InventoryState) -> dict:
    """回复问候、介绍能力或说明当前支持范围。"""

    response = await model.ainvoke(
        [
            SystemMessage(
                content=(
                    "你是运营提效助手，当前支持查询商品库存和检查低库存。"
                    "简短回应用户；涉及其他业务时说明当前支持范围。"
                    "库存数字须通过库存工具查询后提供。"
                )
            ),
            state["messages"][-1],
        ]
    )

    return {"messages": [response]}  # 将回答加入消息记录。


async def call_model(state: InventoryState) -> dict:
    """模型读取当前全部消息，选择工具或生成回答。"""

    rounds = state.get("model_rounds", 0)  # 首轮默认从0开始。

    # 前3轮允许模型选择工具；第4轮要求根据已有信息收尾。
    current_model = inventory_model if rounds < 3 else model

    response = await current_model.ainvoke(state["messages"])

    if response.invalid_tool_calls:
        raise RuntimeError("模型生成的工具请求格式有误")

    return {
        "messages": [response],  # 图会将新消息合并进已有记录。
        "model_rounds": rounds + 1,  # 更新已经执行的模型轮数。
    }


def choose_next(state: InventoryState) -> str:
    """根据最后一条模型消息决定下一步。"""

    last_message = state["messages"][-1]

    if last_message.tool_calls:
        return "tools"  # 模型提出工具请求，进入工具步骤。

    if any(isinstance(message, ToolMessage) for message in state["messages"]):
        return "critic"  # 有查询依据的库存答复进入质量检查。

    return END  # 缺编号等直接澄清保持短路径。


def review_material(state: InventoryState) -> tuple[list[dict], str]:
    """从本次消息中取出工具事实和原始用户要求。"""
    facts = [
        json.loads(message.content)
        for message in state["messages"]
        if isinstance(message, ToolMessage)
    ]
    user_input = next(
        message.content for message in state["messages"]
        if isinstance(message, HumanMessage)
    )
    return facts, user_input


async def check_answer(state: InventoryState) -> dict:
    """读取当前回答和工具事实，写入本次检查结果。"""
    facts, user_input = review_material(state)
    review = await review_inventory_answer(
        facts, state["messages"][-1].content, user_input,
    )
    return {
        "review_passed": review.passed,
        "review_issues": review.issues,
    }  # 评审意见单独保存，messages最后一条继续保留用户可见回答。


def after_review(state: InventoryState) -> str:
    """通过或达到两次修订上限时结束，保留最终质量状态。"""
    if state["review_passed"] or state.get("revise_count", 0) >= 2:
        return END
    return "refine"


async def revise_answer(state: InventoryState) -> dict:
    """只修订回答，本步骤沿用查询结果。"""
    facts, user_input = review_material(state)
    response = await refine_inventory_answer(
        facts, state["messages"][-1].content,
        state["review_issues"], user_input,
    )
    return {
        "messages": [response],
        "revise_count": state.get("revise_count", 0) + 1,
    }


# ToolNode负责执行工具，并返回匹配tool_call_id的ToolMessage。
tool_node = ToolNode(
    [check_inventory],
    handle_tool_errors=False,  # 工具异常交给现有HTTP接口统一处理。
)

def create_quality_graph():
    """组装回答评审子图，沿用现有评审和修订函数。"""
    return (
        StateGraph(InventoryState)  # 与主图使用相同的状态字段。
        .add_node("critic", check_answer)  # 检查回答，写入评审结果。
        .add_node("refine", revise_answer)  # 根据意见修订回答。
        .add_edge(START, "critic")  # 进入子图后先检查。
        .add_conditional_edges(
            "critic",
            after_review,  # 读取是否通过、已经修订几次。
            {"refine": "refine", END: END},
        )
        .add_edge("refine", "critic")  # 修订完再次检查。
        .compile()  # 生成可以执行的子图。
    )

def create_inventory_graph(checkpointer=None):
    """组装库存主图，检查点由外部传入。"""
    return (
        StateGraph(InventoryState)
        .add_node("confirmation", confirm_request)
        .add_node("cancelled", cancel_request)
        .add_node("classifier", classify_request)  # 沿用：分类。
        .add_node("chat", reply_chat)  # 沿用：回答普通问候。
        .add_node("agent", call_model)  # 沿用：模型选择工具或生成回答。
        .add_node("tools", tool_node)  # 沿用：后端执行工具。

        # 修改：这个节点现在执行完整的评审子图。
        .add_node("critic", create_quality_graph())

        .add_edge(START, "confirmation")
        .add_conditional_edges(
            "confirmation", route_confirmation,
            {"classifier": "classifier", "cancelled": "cancelled"},
        )
        .add_edge("cancelled", END)
        .add_conditional_edges(
            "classifier",
            route_request,
            {"agent": "agent", "chat": "chat"},
        )
        .add_edge("chat", END)
        .add_conditional_edges(
            "agent",
            choose_next,
            {"tools": "tools", "critic": "critic", END: END},
        )
        .add_edge("tools", "agent")

        # 修改：子图内部负责评审、修订；子图结束后主图结束。
        .add_edge("critic", END)

        .compile(checkpointer=checkpointer)
    )


inventory_graph = create_inventory_graph()  # 独立练习入口；HTTP使用启动时的持久化图。
