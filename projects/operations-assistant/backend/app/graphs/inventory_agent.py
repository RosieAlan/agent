import json

from langchain_core.messages import SystemMessage, ToolMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from app.core.errors import DependencyUnavailable
from app.tools.inventory import get_demo_inventory


class InventoryState(MessagesState):
    tool_count: int  # 本次请求已经执行的工具调用数。


def create_inventory_graph(model):
    tool_model = model.bind_tools([get_demo_inventory])  # 将工具说明交给模型，尚未查库。
    tool_node = ToolNode([get_demo_inventory], handle_tool_errors=False)
    instructions = SystemMessage(content=(
        "你是库存助手，当前使用演示店铺的合成数据。"
        "查询库存必须先调用get_demo_inventory，收到工具结果后再回答。"
        "缺少商品编号时询问用户，不编造编号或数量。"
        "区分available可售、reserved预留、inbound在途；在途不能当成可售。"
        "工具返回found=false时说明未找到。回答注明模拟数据，禁止声称已发送通知或修改库存。"
    ))

    async def agent(state: InventoryState):
        # 已调用3次工具后，最后一轮使用不绑定工具的模型整理已有结果。
        active_model = tool_model if state["tool_count"] < 3 else model
        reply = await active_model.ainvoke([instructions, *state["messages"]])
        return {"messages": [reply]}  # MessagesState会把新消息合并进历史。

    async def tools(state: InventoryState):
        calls = state["messages"][-1].tool_calls
        if any(call["name"] != get_demo_inventory.name for call in calls):
            raise DependencyUnavailable("模型请求了当前课程未提供的工具")
        if state["tool_count"] + len(calls) > 3:
            raise DependencyUnavailable("本次查询达到工具调用上限，请缩小查询范围")
        patch = await tool_node.ainvoke(state)  # 后端实际执行Python工具，并生成ToolMessage。
        return {**patch, "tool_count": state["tool_count"] + len(calls)}

    def next_step(state: InventoryState):
        return "tools" if state["messages"][-1].tool_calls else END

    return (StateGraph(InventoryState)
        .add_node("agent", agent).add_node("tools", tools)
        .add_edge(START, "agent")
        .add_conditional_edges("agent", next_step, {"tools": "tools", END: END})
        .add_edge("tools", "agent")  # 工具结果回到模型，形成循环。
        .compile())


def format_inventory_answer(result: dict) -> dict:
    answer = result["messages"][-1].content
    if not isinstance(answer, str) or not answer.strip():
        raise DependencyUnavailable("模型未生成有效答复，请重试")
    tool_results = [json.loads(message.content) for message in result["messages"] if isinstance(message, ToolMessage)]
    return {"answer": answer, "data_source": "synthetic_demo", "tool_results": tool_results}
