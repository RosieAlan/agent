"""用户明确填写预算草案与审批决定，金额采用Decimal。"""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProposalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    idempotency_key: UUID  # 同一次提交重复发送时使用同一个值。
    profile_id: str = Field(pattern=r"^[1-9][0-9]{0,19}$")
    campaign_id: str = Field(pattern=r"^[1-9][0-9]{0,19}$")
    proposed_budget: Decimal = Field(gt=0, max_digits=14, decimal_places=2, allow_inf_nan=False)
    reason: str = Field(min_length=1, max_length=1000)


class ProposalDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    proposal_id: UUID
    expected_version: int = Field(ge=1)
    decision: Literal["approve", "reject"]
    reviewer: str = Field(min_length=1, max_length=100)  # 本机演练的填写标识，后续接登录身份。


class ProposalView(BaseModel):
    id: UUID
    profile_id: str
    campaign_id: str
    currency: str
    source_budget: Decimal
    proposed_budget: Decimal
    reason: str
    status: Literal["pending_approval", "approved", "rejected"]
    version: int
    reviewer: str | None
    created_at: datetime
    updated_at: datetime
    execution_status: Literal["not_connected"] = "not_connected"


class ProposalEvent(BaseModel):
    id: UUID
    proposal_id: UUID
    event_type: Literal["created", "approved", "rejected"]
    version: int
    actor: str | None
    created_at: datetime
