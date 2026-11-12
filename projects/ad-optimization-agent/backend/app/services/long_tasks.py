"""启动、读取、恢复同一个分批任务；每次请求结束归还连接。"""
from uuid import uuid4

from app.core.checkpoints import WorkflowConflict, checkpoint_session
from app.graphs.report_batches import build_batch_graph


def view(thread_id, state):
    return {"thread_id": thread_id, "status": state["status"], "error": state.get("error"),
            "scope": state["scope"], "query_count": state["query_count"],
            "replan_count": state["replan_count"], "completed_batches": len(state["completed"]),
            "remaining_batches": state["queue"], "attempts": state["attempts"],
            "summary": state.get("summary"), "answer": state.get("answer", "")}


def start_long_task(body):
    thread_id = f"long:{uuid4()}"
    scope = body.scope.model_dump(mode="json")
    with checkpoint_session(thread_id) as saver:
        state = build_batch_graph(saver).invoke({
            "scope": scope, "queue": [scope.copy()], "target_roas": str(body.target_roas),
            "completed": [], "attempts": [], "query_count": 0, "replan_count": 0,
            "max_queries": body.max_queries, "max_replans": body.max_replans,
            "current_report": None, "status": "running", "error": None, "summary": None,
        }, {"configurable": {"thread_id": thread_id}, "recursion_limit": 100})
        return view(thread_id, state)


def get_long_task(thread_id, *, resume=False):
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 100}
    with checkpoint_session(thread_id) as saver:
        graph = build_batch_graph(saver)
        saved = graph.get_state(config)
        if not saved.values:
            raise LookupError("任务不存在")
        state = saved.values
        if resume:
            if state["status"] != "paused":
                raise WorkflowConflict("当前任务已完成或仍在运行，请读取任务状态")
            if state["query_count"] >= state["max_queries"]:
                raise WorkflowConflict("查询次数已达上限，请缩小范围后创建新任务")
            if state.get("current_report") is not None and state["replan_count"] >= state["max_replans"]:
                raise WorkflowConflict("计划调整次数已达上限，请缩小范围后创建新任务")
            state = graph.invoke({"status": "running", "error": None}, config)
        return view(thread_id, state)
