"""Harness任务输入；查询范围由后端绑定给工具。"""
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.ads import ReportQuery

HarnessThread = Annotated[str, Field(pattern=r"^harness:[0-9a-f-]{36}$")]


class ReportReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    passed: bool
    issues: list[str] = Field(max_length=5)

    @model_validator(mode="after")
    def consistent_result(self):
        if self.passed and self.issues:
            raise ValueError("通过评审时issues应为空")
        if not self.passed and not any(issue.strip() for issue in self.issues):
            raise ValueError("未通过评审时应给出具体问题")
        return self


class HarnessInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    goal: str = Field(default="生成广告复盘，列出事实、待验证原因和下一步检查。", min_length=1, max_length=1000)
    scope: ReportQuery
    target_roas: Decimal = Field(gt=0, le=10000)
