"""图任务的启动、恢复与状态查询。"""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.proposals import ProposalView

ThreadId = Annotated[str, Field(pattern=r"^budget:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")]


class WorkflowStart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposal_id: UUID


class WorkflowResume(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    thread_id: ThreadId
    decision: Literal["approve", "reject"]
    reviewer: str = Field(min_length=1, max_length=100)


class WorkflowView(BaseModel):
    thread_id: str
    status: str
    next_nodes: list[str]
    prepared_at: str | None
    approval_request: dict | None
    proposal: ProposalView | None
