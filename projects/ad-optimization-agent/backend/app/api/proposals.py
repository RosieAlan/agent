"""本机草案与审批接口，记录业务决定；平台写入接口后续接入。"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError

from app.repositories import proposals as repo
from app.schemas.proposals import ProposalCreate, ProposalDecision, ProposalEvent, ProposalView

router = APIRouter(prefix="/proposals", tags=["预算草案与审批"])


def _call(function, *args):
    try:
        return function(*args)
    except repo.ProposalNotFound as error:
        raise HTTPException(404, detail=str(error)) from None
    except repo.ProposalConflict as error:
        raise HTTPException(409, detail=str(error)) from None
    except (SQLAlchemyError, RuntimeError):
        raise HTTPException(503, detail="方案数据服务暂不可用，请检查本机数据库") from None


@router.post("", response_model=ProposalView, status_code=201)
def create(body: ProposalCreate):
    return _call(repo.create_proposal, body)


@router.get("", response_model=list[ProposalView])
def listing(limit: int = Query(default=20, ge=1, le=50)):
    return _call(repo.list_proposals, limit)


@router.get("/detail", response_model=ProposalView)
def detail(proposal_id: UUID):
    return _call(repo.get_proposal, str(proposal_id))


@router.post("/decision", response_model=ProposalView)
def decide(body: ProposalDecision):
    return _call(repo.decide_proposal, body)


@router.get("/events", response_model=list[ProposalEvent])
def events(proposal_id: UUID):
    return _call(repo.list_events, str(proposal_id))
