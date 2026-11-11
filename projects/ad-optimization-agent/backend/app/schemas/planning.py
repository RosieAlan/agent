"""任务计划：操作白名单、参数与依赖规则。"""

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.ads import ReportQuery
from app.schemas.diagnosis import DiagnosticResult


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")  # 拒绝未定义的字段。


class PlanInput(StrictModel):
    goal: str = Field(min_length=1, max_length=2000, pattern=r"\S")
    scope: ReportQuery  # 用户在表单中明确选定的账户、日期及归因范围。


class TaskBase(StrictModel):
    id: str = Field(pattern=r"^T[1-9][0-9]?$", description="任务编号，例如T1")
    depends_on: list[str] = Field(description="必须先完成的任务编号列表")


class QueryTask(TaskBase):
    action: Literal["query_reports"]
    args: ReportQuery


class FilterArgs(StrictModel):
    target_roas: Decimal = Field(gt=0, allow_inf_nan=False, description="用户明确提供的目标ROAS")


class FilterTask(TaskBase):
    action: Literal["find_low_roas"]
    args: FilterArgs


class ReviewTask(TaskBase):
    action: Literal["write_review"]
    args: StrictModel  # 当前复盘任务没有额外参数，返回空对象。


Task = Annotated[QueryTask | FilterTask | ReviewTask, Field(discriminator="action")]


class TaskPlan(StrictModel):
    status: Literal["ready", "clarification_required"]
    question: str = Field(description="需要澄清时填写问题，ready时为空字符串")
    tasks: list[Task] = Field(max_length=3)

    @model_validator(mode="after")
    def check_dependencies(self):
        if self.status == "clarification_required":
            if self.tasks or not self.question.strip():
                raise ValueError("澄清计划需要问题及空任务列表")
            return self
        if self.question.strip() or not self.tasks:
            raise ValueError("可执行计划需要任务列表及空问题")
        by_id = {task.id: task for task in self.tasks}
        by_action = {task.action: task for task in self.tasks}
        if len(by_id) != len(self.tasks) or len(by_action) != len(self.tasks):
            raise ValueError("任务编号和操作应保持唯一")
        query = by_action.get("query_reports")
        if query is None or query.depends_on:
            raise ValueError("查询任务必须存在且无前置依赖")
        for task in self.tasks:
            if len(set(task.depends_on)) != len(task.depends_on):
                raise ValueError("依赖编号重复")
            if any(dep not in by_id or dep == task.id for dep in task.depends_on):
                raise ValueError("依赖任务不存在或依赖自身")
            if task.action == "find_low_roas" and task.depends_on != [query.id]:
                raise ValueError("筛选任务需要依赖查询任务")
            if task.action == "write_review":
                previous = by_action.get("find_low_roas", query)
                if task.depends_on != [previous.id]:
                    raise ValueError("复盘任务需要依赖筛选结果或原始查询结果")
        return self  # 当前三类操作的依赖规则同时保证无循环依赖。


class TaskRun(BaseModel):
    id: str
    action: str
    status: Literal["pending", "running", "completed", "failed", "blocked"]
    result: dict | None
    error: str | None
    duration_ms: float | None = None


class ExecutionResponse(BaseModel):
    status: Literal["completed", "needs_attention", "clarification_required"]
    answer: str
    execution_order: list[str]
    tasks: list[TaskRun]


class AnalysisResponse(ExecutionResponse):
    plan: TaskPlan  # 一次响应同时返回模型计划与实际执行结果。
    diagnosis: DiagnosticResult | None = None  # 诊断与评审状态独立于SQL任务状态。
