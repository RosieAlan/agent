"""任务计划预览HTTP入口。"""

import asyncio
import logging

from fastapi import APIRouter, HTTPException
from langchain_core.exceptions import OutputParserException
from openai import APIError, APITimeoutError
from pydantic import ValidationError

from app.schemas.planning import PlanInput, TaskPlan
from app.services.planning import create_plan

router = APIRouter(prefix="/assistant", tags=["任务规划"])
logger = logging.getLogger("uvicorn.error")


@router.post("/plan", response_model=TaskPlan)
async def preview_plan(body: PlanInput):
    try:
        async with asyncio.timeout(30):  # 包含模型调用和解析的整体等待上限。
            return await create_plan(body)
    except (TimeoutError, APITimeoutError):
        raise HTTPException(504, detail="任务规划超时，请稍后重试") from None
    except RuntimeError:
        raise HTTPException(503, detail="规划模型配置暂不可用") from None
    except (ValidationError, OutputParserException, ValueError, APIError) as error:
        logger.warning("ad_plan_failed error_type=%s", type(error).__name__)
        raise HTTPException(502, detail="任务计划生成失败，请重试或补充要求") from None
