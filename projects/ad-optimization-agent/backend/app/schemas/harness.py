"""Harness任务输入；查询范围由后端绑定给工具。"""
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.ads import ReportQuery

HarnessThread = Annotated[str, Field(pattern=r"^harness:[0-9a-f-]{36}$")]


class HarnessInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    goal: str = Field(default="生成广告复盘，列出事实、待验证原因和下一步检查。", min_length=1, max_length=1000)
    scope: ReportQuery
    target_roas: Decimal = Field(gt=0, le=10000)
