from pydantic import BaseModel, ConfigDict, Field
from typing import Literal


class AssistantInput(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,  # 去掉输入两端空白。
        extra="forbid",             # 拒绝未定义的字段。
    )

    input: str = Field(min_length=1, max_length=1000)


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
    tool_results: list[dict]          # 本次实际执行的工具及结果。
    quality: AnswerQuality  # 显式保留评审状态，达到上限仍按实际结果展示。


class TaskAnswer(AssistantResponse):
    task_id: str  # 本次库存任务编号，用于查询与恢复。


class TaskStatus(BaseModel):
    task_id: str
    status: Literal["completed", "incomplete"]
    next_nodes: list[str]  # 快照保存的待执行节点。
    model_rounds: int
    revise_count: int
    result: AssistantResponse | None = None
