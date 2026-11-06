import json  # 将工具结果转换成消息中的JSON文本。

from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from core.model import model
from tools import check_inventory
from graphs.inventory import inventory_graph  # 导入已编译的库存流程。

inventory_model = model.bind_tools([check_inventory])


def build_messages(input_text: str) -> list:
    """统一组装系统规则和用户问题。"""
    return [
        SystemMessage(
            content=(
                "你是库存助手。"
                "查询或检查库存时使用check_inventory工具。"
                "sku必须来自用户提供的商品编号，缺少时先询问。"
                "阈值采用用户指定值，未指定时默认20。"
                "收到工具结果后才能描述库存数量。"
                "分别列出各店铺可售、预留和在途库存，"
                "低库存判断及差额以工具结果为准。"
                "在途库存单独展示。"
                "items为空时说明未找到库存记录。"
                "回答注明模拟数据来源。"
                "当前功能只执行查询和判断。"
            )
        ),
        HumanMessage(content=input_text),
    ]


async def plan_inventory_tool(input_text: str) -> dict:
    """保留已有功能：仅查看模型生成的工具请求。"""
    response = await inventory_model.ainvoke(build_messages(input_text))

    return {
        "content": response.content if isinstance(response.content, str) else "",
        "tool_calls": response.tool_calls,
    }


async def run_inventory_assistant(input_text: str) -> dict:
    """运行库存图，再整理成现有HTTP响应格式。"""

    result = await inventory_graph.ainvoke(
        {
            "messages": build_messages(input_text),  # 沿用已有系统规则。
            "model_rounds": 0,  # 每次HTTP请求从第0轮开始。
        },
        config={"recursion_limit": 12},  # 图执行步数的额外保护。
    )

    messages = result["messages"]
    final = messages[-1]  # 正常结束时，最后一条是模型回答。

    if not isinstance(final.content, str) or not final.content.strip():
        raise RuntimeError("模型未生成有效答复")

    # 将模型生成的工具请求按编号保存，方便匹配执行结果。
    calls_by_id = {}

    for message in messages:
        for call in getattr(message, "tool_calls", []):
            calls_by_id[call["id"]] = call

    tool_results = []

    for message in messages:
        if isinstance(message, ToolMessage):
            call = calls_by_id[message.tool_call_id]

            tool_results.append(
                {
                    "name": call["name"],
                    "args": call["args"],
                    "tool_call_id": message.tool_call_id,
                    "result": json.loads(message.content),
                }
            )

    return {
        "answer": final.content,
        "tool_results": tool_results,
    }
