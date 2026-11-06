from langchain_core.messages import HumanMessage, SystemMessage

from core.model import model
from tools import check_inventory

# 应用加载此模块时绑定工具说明。
inventory_model = model.bind_tools([check_inventory])


async def plan_inventory_tool(input_text: str) -> dict:
    """根据用户问题，生成库存工具调用请求。"""

    messages = [
        SystemMessage(content=(
            "你是库存助手。"
            "用户要求查询或检查库存时，使用check_inventory工具。"
            "sku必须来自用户提供的商品编号。"
            "缺少商品编号时询问用户。"
            "用户指定阈值时采用指定值，否则采用默认20。"
            "获得工具结果后才能描述库存数量。"
        )),
        HumanMessage(content=input_text),  # 用户本次问题。
    ]

    # 发起一次真实模型请求，等待模型生成回复。
    response = await inventory_model.ainvoke(messages)

    return {
        # 当前模型的文字回复；工具调用时可能为空。
        "content": (
            response.content
            if isinstance(response.content, str)
            else ""
        ),
        "tool_calls": response.tool_calls,  # 待后端执行的工具请求。
    }