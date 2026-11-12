"""持久化分批查询：超限后调整剩余批次，完整取数后汇总。"""
from datetime import date, timedelta
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.ads import fetch_reports
from app.schemas.ads import ReportQuery
from app.schemas.planning import FilterTask, ReviewTask
from app.services.execution import _filter, _review


class BatchState(TypedDict, total=False):
    scope: dict
    target_roas: str
    queue: list[dict]
    completed: list[dict]
    attempts: list[dict]
    query_count: int
    replan_count: int
    max_queries: int
    max_replans: int
    current_report: dict | None
    status: str
    error: str | None
    summary: dict | None
    answer: str


def query_batch(state: BatchState):
    if state["query_count"] >= state["max_queries"]:
        return {"status": "paused", "error": "已达查询次数上限，请缩小范围后创建新任务"}
    query = ReportQuery.model_validate(state["queue"][0])
    event = {"query": query.model_dump(mode="json")}
    count = state["query_count"] + 1
    try:
        report = fetch_reports(query)  # 公司源库保持只读。
    except SQLAlchemyError:
        return {"status": "paused", "error": "报表数据源暂不可用，可恢复本任务重试当前批次",
                "query_count": count, "current_report": None,
                "attempts": [*state["attempts"], {**event, "status": "failed"}]}
    if report is None:
        return {"status": "paused", "error": "广告账户不存在，请核对范围后创建新任务",
                "query_count": count, "current_report": None,
                "attempts": [*state["attempts"], {**event, "status": "failed"}]}
    if report["has_more"]:
        return {"current_report": report, "query_count": count,
                "attempts": [*state["attempts"], {**event, "status": "needs_replan"}]}
    return {"completed": [*state["completed"], {"query": event["query"], "report": report}],
            "queue": state["queue"][1:], "current_report": None, "query_count": count,
            "attempts": [*state["attempts"], {**event, "status": "completed"}]}


def replan_batches(state: BatchState):
    if state["replan_count"] >= state["max_replans"]:
        return {"status": "paused", "error": "已达计划调整上限，请缩小范围后创建新任务"}
    current = state["queue"][0]
    start, end = date.fromisoformat(current["start_date"]), date.fromisoformat(current["end_date"])
    completed = state["completed"]
    if start < end and current["offset"] == 0:
        middle = start + (end - start) // 2
        remaining = [
            {**current, "end_date": middle.isoformat()},
            {**current, "start_date": (middle + timedelta(days=1)).isoformat()},
        ]  # 两个日期段无重叠，合起来与原范围完全相同。
        strategy = "split_dates"  # 当前超限页丢弃；两个子批次重新取，避免重复合计。
    else:
        remaining = [{**current, "offset": current["offset"] + current["limit"]}]
        ReportQuery.model_validate(remaining[0])  # 分页参数继续执行Schema边界校验。
        completed = [*completed, {"query": current, "report": state["current_report"]}]
        strategy = "next_page"  # 单日继续分页，当前页已取得的行保留。
    return {"queue": [*remaining, *state["queue"][1:]], "completed": completed,
            "replan_count": state["replan_count"] + 1, "current_report": None,
            "attempts": [*state["attempts"], {"status": "replanned", "strategy": strategy,
                                            "query": current, "replacement": remaining}]}


def finish_report(state: BatchState):
    report = {"data_source": "company_test_readonly", "offset": 0, "has_more": False,
              "profile": state["completed"][0]["report"]["profile"],
              "items": [row for batch in state["completed"] for row in batch["report"]["items"]]}
    filtered = _filter(FilterTask(id="T2", action="find_low_roas", depends_on=["T1"],
                                 args={"target_roas": state["target_roas"]}), report)
    answer = _review(ReviewTask(id="T3", action="write_review", depends_on=["T2"], args={}), filtered)
    return {"status": "completed", "error": None, "summary": filtered, "answer": answer["answer"]}


def next_step(state: BatchState):
    if state["status"] == "paused":
        return END
    if state.get("current_report") is not None:
        return "replan"
    return "query" if state["queue"] else "finish"


def build_batch_graph(checkpointer):
    return (StateGraph(BatchState)
            .add_node("query", query_batch)
            .add_node("replan", replan_batches)
            .add_node("finish", finish_report)
            .add_edge(START, "query")
            .add_conditional_edges("query", next_step)
            .add_conditional_edges("replan", next_step)
            .add_edge("finish", END)
            .compile(checkpointer=checkpointer))
