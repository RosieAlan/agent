from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SupervisorInput(BaseModel):
    """专家选择接口接收的用户问题。"""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    input: str = Field(min_length=1, max_length=1000)  # 拒绝空问题和过长输入。


class SupervisorPlan(BaseModel):
    """模型输出的专家名单；空名单表示当前问题需要说明或超出能力。"""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    experts: list[Literal["inventory", "replenishment"]] = Field(
        max_length=2,
        description="inventory处理库存；replenishment处理补货建议；无法确定时返回空列表",
    )
    reason: str = Field(
        min_length=1,
        max_length=500,
        description="简短说明选择依据，空名单时说明需要用户补充什么",
    )

    @field_validator("experts")
    @classmethod
    def unique_experts(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("专家名单中每个专家只能出现一次")
        return value


class TeamResponse(SupervisorPlan):
    # 继承SupervisorPlan，继续包含experts和reason。
    status: Literal["completed", "partial_success", "needs_clarification", "not_found"]
    answer: str

    inventory_report: str = ""  # 未选中的专家保留空字符串。
    replenishment_report: str = ""
    expert_errors: dict[Literal["inventory", "replenishment"], str] = Field(
        default_factory=dict,  # 每个响应有自己的错误字典。
    )
    quality_status: Literal["skipped", "passed", "needs_review"] = "skipped"
    review_issues: list[str] = Field(default_factory=list)
    revise_count: int = Field(default=0, ge=0, le=2)  # 硬上限：最多修订两次。


class ReportReview(BaseModel):
    """评审模型返回的格式；具体意见用于下一步修订。"""

    model_config = ConfigDict(extra="forbid")
    passed: bool
    issues: list[str] = Field(max_length=5)
