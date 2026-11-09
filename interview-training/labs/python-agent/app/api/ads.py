from fastapi import APIRouter, HTTPException
from langchain_core.exceptions import OutputParserException
from openai import APITimeoutError, OpenAIError
from sqlalchemy.exc import (
    OperationalError,
    SQLAlchemyError,
    TimeoutError as PoolTimeoutError,
)
from app.schemas.requirements import RequirementInput
from app.services.llm_service import run_ad_tool, request_ad_tool
from app.tools.ad_tools import get_ad_report
from app.graphs.ad_report_graph import ad_graph, AdReportNotFound
from app.services.ad_intent_service import (
    AdIntentResult,
    classify_ad_intent,
)
from app.graphs.ad_chat_graph import ad_chat_graph

router = APIRouter(tags=["ads"])  # 收集广告接口，由app/main.py登记。


@router.get("/ads/report/{campaign_id}")
def ad_report(campaign_id: str):
    try:
        return get_ad_report(campaign_id)  # 调用刚才改好的查询函数。

    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail="未找到可访问的广告报表",
        ) from error

    except (OperationalError, PoolTimeoutError) as error:
        raise HTTPException(
            status_code=503,
            detail="报表数据库暂时不可用",
        ) from error

    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=500,
            detail="报表查询失败，请联系维护人员",
        ) from error


@router.post("/ads/tool-request")
async def ad_tool_request(body: RequirementInput):
    try:
        # main.py → llm_service.py → 带工具说明的模型。
        # 当前返回tool_calls，实际工具执行在下一块接入。
        return await request_ad_tool(body.input)

    except APITimeoutError as error:
        raise HTTPException(
            status_code=504,
            detail="模型请求超时",
        ) from error

    except OutputParserException as error:
        raise HTTPException(
            status_code=502,
            detail="模型工具参数解析失败",
        ) from error

    except OpenAIError as error:
        raise HTTPException(
            status_code=502,
            detail="模型服务调用失败",
        ) from error


@router.post("/ads/chat")
async def ad_chat(body: RequirementInput):
    try:
        # 模型选工具 → 后端执行 → 回填结果 → 模型回答。
        return await run_ad_tool(body.input)

    except APITimeoutError as error:
        raise HTTPException(
            status_code=504,
            detail="模型请求超时",
        ) from error

    except OutputParserException as error:
        raise HTTPException(
            status_code=502,
            detail="模型工具请求解析失败",
        ) from error

    except OpenAIError as error:
        raise HTTPException(
            status_code=502,
            detail="模型服务调用失败",
        ) from error

    except (OperationalError, PoolTimeoutError) as error:
        raise HTTPException(
            status_code=503,
            detail="业务数据库暂时不可用",
        ) from error

    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=500,
            detail="业务数据查询失败，请联系维护人员",
        ) from error


@router.get("/ads/graph/{campaign_id}")
def ad_graph_report(campaign_id: str):
    try:
        result = ad_graph.invoke(
            {
                "user_id": "user-001",  # 当前本地演练身份，由后端指定。
                "store_id": "store-A",
                "campaign_id": campaign_id,
                "report": {},
                "roas": None,
                "summary": "",
            }
        )  # 收到请求后，才真正执行图中的三个函数。

        return {
            "campaign_id": result["campaign_id"],
            "data_source": result["report"]["data_source"],
            "spend": result["report"]["spend"],
            "attributed_sales": result["report"]["attributed_sales"],
            "roas": result["roas"],
            "summary": result["summary"],
        }

    except AdReportNotFound as error:
        raise HTTPException(404, "未找到可访问的广告报表") from error

    except (OperationalError, PoolTimeoutError) as error:
        raise HTTPException(503, "报表数据库暂时不可用") from error

    except SQLAlchemyError as error:
        raise HTTPException(500, "报表查询失败") from error


@router.post("/ads/intent", response_model=AdIntentResult)
async def ad_intent(body: RequirementInput):
    # RequirementInput继续校验input为非空字符串。
    try:
        return await classify_ad_intent(
            body.input,  # 将用户原文传给分类服务。
        )

    except APITimeoutError as error:
        # 请求模型超时，对浏览器返回504。
        raise HTTPException(
            status_code=504,
            detail="意图识别超时，请稍后重试",
        ) from error

    except OutputParserException as error:
        # 模型返回结果无法通过解析或字段校验。
        raise HTTPException(
            status_code=502,
            detail="意图识别结果格式错误",
        ) from error

    except OpenAIError as error:
        # 模型供应商请求失败，保留内部错误详情在后端排查。
        raise HTTPException(
            status_code=502,
            detail="意图识别服务暂时不可用",
        ) from error


@router.post("/ads/graph-chat")
async def ad_graph_chat(body: RequirementInput):
    try:
        result = await ad_chat_graph.ainvoke(
            {
                "input": body.input,  # 用户本次输入。
                "user_id": "user-001",  # 当前本地演练身份，由后端指定。
                "store_id": "store-A",
                "campaign_id": "",
                "intent": "",
                "reason": "",
                "report": {},
                "roas": None,
                "summary": "",
            }
        )

        needs_clarification = result[
            "intent"
        ] == "clarify" or (  # 新增：任务本身没有判断清楚。
            result["intent"] != "chat"
            and not result["campaign_id"]  # 已知任务类型，但缺少编号。
        )

        return {
            "status": ("need_clarification" if needs_clarification else "completed"),
            "intent": result["intent"],
            "reason": result["reason"],
            "answer": result["summary"],
            "report": result["report"],
            "roas": result["roas"],
            "classification_source": result["classification_source"],
        }

    except AdReportNotFound as error:
        raise HTTPException(404, "未找到可访问的广告报表") from error

    except (OperationalError, PoolTimeoutError) as error:
        raise HTTPException(503, "报表数据库暂时不可用") from error

    except SQLAlchemyError as error:
        raise HTTPException(500, "报表查询失败") from error

    except APITimeoutError as error:
        raise HTTPException(504, "意图识别超时，请稍后重试") from error

    except OutputParserException as error:
        raise HTTPException(502, "意图识别结果格式错误") from error

    except OpenAIError as error:
        raise HTTPException(502, "意图识别服务暂时不可用") from error
