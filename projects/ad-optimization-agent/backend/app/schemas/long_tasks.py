from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.ads import ReportQuery

LongThread = Annotated[str, Field(pattern=r"^long:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")]


class LongTaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope: ReportQuery
    target_roas: Decimal = Field(gt=0, le=10000, allow_inf_nan=False)
    max_queries: int = Field(default=12, ge=1, le=20)
    max_replans: int = Field(default=6, ge=0, le=10)

    @model_validator(mode="after")
    def full_scope(self):
        if self.scope.offset != 0:
            raise ValueError("完整分析从offset=0开始")
        return self


class LongTaskResume(BaseModel):
    model_config = ConfigDict(extra="forbid")
    thread_id: LongThread
