from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode

from core.model import model
from tools import check_inventory
from typing import Literal  # 将分类值限定在指定字符串中。

from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage

# 绑定工具：让模型获得库存工具的说明和参数格式。
inventory_model = model.bind_tools([check_inventory])


class InventoryState(MessagesState):
    """本次流程共享的消息、模型轮数和请求类别。"""

    model_rounds: int
    intent: Literal["inventory", "chat"]  # 新增：分类结果。


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

    return END  # 模型已经直接回答，结束流程。


# ToolNode负责执行工具，并返回匹配tool_call_id的ToolMessage。
tool_node = ToolNode(
    [check_inventory],
    handle_tool_errors=False,  # 工具异常交给现有HTTP接口统一处理。
)


inventory_graph = (
    StateGraph(InventoryState)
    .add_node("classifier", classify_request)  # 新增：识别请求类别。
    .add_node("chat", reply_chat)  # 新增：直接回答。
    .add_node("agent", call_model)  # 沿用：模型选择库存工具。
    .add_node("tools", tool_node)  # 沿用：执行库存工具。
    .add_edge(START, "classifier")  # 入口先分类。
    .add_conditional_edges(
        "classifier",
        route_request,  # 分类完成后，读取intent选择路径。
        {"agent": "agent", "chat": "chat"},
    )
    .add_edge("chat", END)  # 问候回复完成后结束。
    .add_conditional_edges(
        "agent",
        choose_next,  # 沿用：判断继续执行工具或结束。
        {"tools": "tools", END: END},
    )
    .add_edge("tools", "agent")  # 沿用：工具结果交回模型。
    .compile()
)
