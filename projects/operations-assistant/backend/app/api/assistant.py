import asyncio

from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage
from openai import APIError
from pydantic import ValidationError

from app.core.model import get_model
from app.graphs.inventory_agent import create_inventory_graph, format_inventory_answer
from app.schemas.assistant import AssistantInput, AssistantOutput

router = APIRouter(prefix="/demo/assistant", tags=["demo-assistant"])


@router.post("/chat", response_model=AssistantOutput)
async def chat(body: AssistantInput):
    try:
        async with asyncio.timeout(60):  # 限制整次Agent请求耗时。
            graph = create_inventory_graph(get_model())
            result = await graph.ainvoke({"messages": [HumanMessage(body.input)], "tool_count": 0}, {"recursion_limit": 10})
            return format_inventory_answer(result)
    except TimeoutError as error:
        raise HTTPException(504, "模型响应超时，本次查询未完成") from error
    except APIError as error:
        raise HTTPException(502, "模型服务调用失败，请检查后端配置或稍后重试") from error
    except ValidationError as error:
        raise HTTPException(502, "模型生成的工具参数不符合要求") from error
