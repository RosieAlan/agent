"""任务规划、执行与合并分析HTTP入口。"""

import asyncio
import logging

from fastapi import APIRouter, HTTPException
from langchain_core.exceptions import OutputParserException
from openai import APIError, APITimeoutError
from pydantic import ValidationError

from app.schemas.planning import AnalysisResponse, ExecutionResponse, PlanInput, TaskPlan
from app.services.execution import execute_plan
from app.services.diagnosis import diagnose_execution
from app.services.planning import create_plan

router = APIRouter(prefix="/assistant", tags=["任务规划"])
logger = logging.getLogger("uvicorn.error")


async def _checked_plan(body: PlanInput):
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


@router.post("/plan", response_model=TaskPlan)
async def preview_plan(body: PlanInput):
    return await _checked_plan(body)


@router.post("/execute", response_model=ExecutionResponse)
def run_plan(body: TaskPlan):
    return execute_plan(body)  # 同步SQL由FastAPI线程池执行，任务结果逐项返回。


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze(body: PlanInput):
    plan = await _checked_plan(body)  # 第一步：模型规划及计划校验。
    result = await asyncio.to_thread(execute_plan, plan)  # 第二步：线程中执行同步SQL与计算。
    diagnosis = await diagnose_execution(body.goal, result)  # 第三步：同一证据做诊断与评审，最多修订一次。
    return {"plan": plan, **result, "diagnosis": diagnosis}  # 模型失败时保留事实清单。
