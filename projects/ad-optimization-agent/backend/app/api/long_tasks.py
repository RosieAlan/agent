from fastapi import APIRouter, HTTPException
from pymysql import MySQLError
from sqlalchemy.exc import SQLAlchemyError

from app.core.checkpoints import WorkflowConflict
from app.schemas.long_tasks import LongTaskInput, LongTaskResume, LongThread
from app.services.long_tasks import get_long_task, start_long_task

router = APIRouter(prefix="/long-tasks", tags=["长任务与规则重规划"])


def _call(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except WorkflowConflict as error:
        raise HTTPException(409, detail=str(error)) from None
    except LookupError as error:
        raise HTTPException(404, detail=str(error)) from None
    except (SQLAlchemyError, MySQLError, RuntimeError):
        raise HTTPException(503, detail="任务状态服务暂不可用，请检查本机MySQL") from None


@router.post("/start")
def start(body: LongTaskInput):
    return _call(start_long_task, body)


@router.get("/state")
def state(thread_id: LongThread):
    return _call(get_long_task, thread_id)


@router.post("/resume")
def resume(body: LongTaskResume):
    return _call(get_long_task, body.thread_id, resume=True)
