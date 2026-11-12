"""人工确认图：启动、查询、恢复。"""

from fastapi import APIRouter, HTTPException
from pymysql import MySQLError
from sqlalchemy.exc import SQLAlchemyError

from app.core.checkpoints import WorkflowConflict
from app.repositories.proposals import ProposalConflict, ProposalNotFound
from app.schemas.workflows import ThreadId, WorkflowResume, WorkflowStart, WorkflowView
from app.services.workflows import read_workflow, resume_workflow, start_workflow

router = APIRouter(prefix="/workflows", tags=["LangGraph持久化与人工恢复"])


def _call(function, *args):
    try:
        return function(*args)
    except ProposalNotFound as error:
        raise HTTPException(404, detail=str(error)) from None
    except (ProposalConflict, WorkflowConflict) as error:
        raise HTTPException(409, detail=str(error)) from None
    except (SQLAlchemyError, MySQLError, RuntimeError):
        raise HTTPException(503, detail="图状态服务暂不可用，请检查MySQL及检查点初始化") from None


@router.post("/start", response_model=WorkflowView)
def start(body: WorkflowStart):
    return _call(start_workflow, str(body.proposal_id))


@router.get("/state", response_model=WorkflowView)
def state(thread_id: ThreadId):
    return _call(read_workflow, thread_id)


@router.post("/resume", response_model=WorkflowView)
def resume(body: WorkflowResume):
    return _call(resume_workflow, body)
