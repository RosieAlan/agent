from pydantic import BaseModel, ConfigDict, Field
from typing import Literal


class AssistantInput(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,  # 去掉输入两端空白。
        extra="forbid",  # 拒绝未定义的字段。
    )

    input: str = Field(min_length=1, max_length=1000)
    require_confirmation: bool = Field(
        default=False, strict=True,
    )  # 用户主动开启执行前确认；原有查询默认直接执行。


class ToolPlanResponse(BaseModel):
    content: str
    tool_calls: list[dict]


class AnswerQuality(BaseModel):
    """质量结果与修订次数，前端据此展示通过或待复核。"""

    status: Literal["passed", "needs_review", "skipped"]
    revise_count: int = Field(ge=0, le=2)
    issues: list[str]


class AssistantResponse(BaseModel):
    answer: str = Field(min_length=1)  # 用户可读的最终答复。
    tool_results: list[dict]  # 本次实际执行的工具及结果。
    quality: AnswerQuality  # 显式保留评审状态，达到上限仍按实际结果展示。


class TaskAnswer(AssistantResponse):
    task_id: str  # 本次库存任务编号，用于查询与恢复。


class TaskStatus(BaseModel):
    """任务查询和人工确认接口返回的任务状态。"""

    task_id: str  # 原任务编号。

    status: Literal[
        "completed",
        "incomplete",
        "waiting_confirmation",
    ]  # 前端根据状态展示结果、恢复按钮或确认按钮。

    next_nodes: list[str]  # 后续等待执行的节点。
    model_rounds: int  # 已执行的模型轮数。
    revise_count: int  # 已修订次数。

    confirmations: list[dict] = Field(
        default_factory=list,
    )  # 待确认内容；必须缩进到这个类里面。

    result: AssistantResponse | None = None  # 任务完成后保存最终回答。


class ConfirmationInput(BaseModel):
    """用户提交的确认结果。"""

    model_config = ConfigDict(
        extra="forbid",
    )  # 请求中出现额外字段时返回422。

    approved: bool = Field(
        strict=True,
    )  # 只接受JSON的true或false，防止字符串被自动转换。
