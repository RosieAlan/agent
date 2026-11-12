"""DeepAgent任务入口与已保存成果查询。"""
import logging

from fastapi import APIRouter, HTTPException
from openai import APIError
from pymysql import MySQLError
from sqlalchemy.exc import SQLAlchemyError

from app.core.checkpoints import WorkflowConflict
from app.schemas.harness import HarnessInput, HarnessThread
from app.services.harness import read_harness, run_harness

router = APIRouter(prefix="/harness", tags=["DeepAgent任务清单与文件"])
logger = logging.getLogger("uvicorn.error")


def _call(function, argument):
    try:
        return function(argument)
    except WorkflowConflict as error:
        raise HTTPException(409, detail=str(error)) from None
    except ValueError as error:
        raise HTTPException(422, detail=str(error)) from None
    except APIError as error:
        logger.warning("harness_model_error type=%s", type(error).__name__)
        raise HTTPException(502, detail="Harness模型调用失败，请检查模型配置与额度") from None
    except (SQLAlchemyError, MySQLError, RuntimeError) as error:
        logger.warning("harness_unavailable type=%s", type(error).__name__)
        raise HTTPException(503, detail="Harness任务服务暂不可用，请检查数据库和配置") from None


@router.post("/run")
def run(body: HarnessInput):
    return _call(run_harness, body)


@router.get("/state")
def state(thread_id: HarnessThread):
    result = _call(read_harness, thread_id)
    if result is None:
        raise HTTPException(404, detail="Harness任务不存在")
    return result
