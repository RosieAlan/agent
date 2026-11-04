from fastapi import APIRouter, HTTPException
from langchain_core.exceptions import OutputParserException
from openai import APITimeoutError, OpenAIError
from sqlalchemy.exc import OperationalError, SQLAlchemyError, TimeoutError as PoolTimeoutError
from app.schemas.requirements import RequirementInput
from app.services.llm_service import run_ad_tool, request_ad_tool
from app.tools.ad_tools import get_ad_report

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
