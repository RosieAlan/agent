"""诊断、评审与有限修订的输出约定。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=1, max_length=500, description="有依据的问题描述")
    evidence_ids: list[str] = Field(min_length=1, max_length=10, description="引用E1等证据编号")
    possible_causes: list[str] = Field(max_length=3, description="明确作为待验证假设的可能原因")
    next_checks: list[str] = Field(min_length=1, max_length=3, description="建议补查的数据")


class DiagnosticDraft(BaseModel):
    """诊断输出，只包含findings字段。"""
    model_config = ConfigDict(extra="forbid")
    findings: list[Finding] = Field(min_length=1, max_length=5)


class DiagnosticReview(BaseModel):
    """评审输出，只包含passed与issues两个字段。"""
    model_config = ConfigDict(extra="ignore")  # 提取评审字段，供应商回显的输入资料不进入结果。
    passed: bool
    issues: list[str] = Field(default_factory=list, max_length=5, description="具体问题；通过时为空数组")

    @model_validator(mode="after")
    def consistent_result(self):
        if self.passed == bool(self.issues):
            raise ValueError("评审通过时意见为空，未通过时需要具体意见")
        return self


class DiagnosticResult(BaseModel):
    status: Literal["passed", "needs_review", "unavailable", "skipped"]
    draft: DiagnosticDraft | None = None
    review: DiagnosticReview | None = None
    revise_count: int = Field(default=0, ge=0, le=1)
    evidence: dict = Field(default_factory=dict)  # 与模型共用的最小汇总快照。
    references: dict[str, str] = Field(default_factory=dict)  # E编号→活动编号，仅在后端响应中附加。
    warnings: list[str] = Field(default_factory=list)
