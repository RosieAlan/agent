from fastapi import APIRouter, HTTPException
from langchain_core.exceptions import OutputParserException
from openai import APITimeoutError, OpenAIError
from pydantic import ValidationError
from app.schemas.requirements import RequirementInput, RequirementResult
from app.prompts.requirements import build_messages
from app.services.llm_service import extract_requirement

router = APIRouter(tags=["requirements"])  # 收集预览、需求抽取接口。


@router.post("/messages/preview")
def preview_messages(body: RequirementInput):
    return {
        "messages": build_messages(body.input),
    }



@router.post(
    "/requirements/structured",
    response_model=RequirementResult,  # 检查并整理接口返回的数据。
)
async def structured_requirement(body: RequirementInput):
    try:
        # main.py → llm_service.py → 模型 → 结果Schema校验。
        return await extract_requirement(body.input)

    except APITimeoutError as error:
        raise HTTPException(
            status_code=504,
            detail="模型请求超时，请稍后重试",
        ) from error

    except (ValidationError, OutputParserException) as error:
        raise HTTPException(
            status_code=502,
            detail="模型返回的数据未通过结构校验",
        ) from error

    except OpenAIError as error:
        raise HTTPException(
            status_code=502,
            detail="模型服务调用失败，请检查后端配置及服务状态",
        ) from error
