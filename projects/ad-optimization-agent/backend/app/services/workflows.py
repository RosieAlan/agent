"""每次请求重建图，使用相同thread_id加载MySQL中的进度。"""

from langgraph.types import Command

from app.core.checkpoints import WorkflowConflict, checkpoint_session
from app.graphs.approval import create_approval_graph
from app.repositories.proposals import ProposalConflict, ProposalNotFound, get_proposal
from app.schemas.workflows import WorkflowResume


def _view(graph, config, thread_id):
    snapshot = graph.get_state(config)
    if not snapshot.values:
        raise ProposalNotFound("图任务不存在，请先启动任务")
    interrupts = [item.value for task in snapshot.tasks for item in task.interrupts]
    error = any(task.error for task in snapshot.tasks)
    return {
        "thread_id": thread_id,
        "status": "needs_attention" if error else snapshot.values.get("status", "incomplete"),
        "next_nodes": list(snapshot.next), "prepared_at": snapshot.values.get("prepared_at"),
        "approval_request": interrupts[0] if interrupts else None,
        "proposal": snapshot.values.get("proposal"),
    }


def start_workflow(proposal_id: str):
    thread_id = f"budget:{proposal_id}"
    config = {"configurable": {"thread_id": thread_id}}
    with checkpoint_session(thread_id) as saver:
        graph = create_approval_graph(saver)
        if not graph.get_state(config).values:
            if get_proposal(proposal_id)["status"] != "pending_approval":
                raise ProposalConflict("方案已处理，请使用待审批方案启动任务")
            graph.invoke({"proposal_id": proposal_id}, config)  # 运行到interrupt后返回。
        return _view(graph, config, thread_id)


def read_workflow(thread_id: str):
    with checkpoint_session(thread_id) as saver:
        return _view(create_approval_graph(saver), {"configurable": {"thread_id": thread_id}}, thread_id)


def resume_workflow(body: WorkflowResume):
    config = {"configurable": {"thread_id": body.thread_id}}
    with checkpoint_session(body.thread_id) as saver:
        graph = create_approval_graph(saver)
        snapshot = graph.get_state(config)
        if not snapshot.values:
            raise ProposalNotFound("图任务不存在")
        if not any(task.interrupts for task in snapshot.tasks):
            raise WorkflowConflict("任务当前没有待回答的中断，请查看现有状态")
        graph.invoke(Command(resume={"decision": body.decision, "reviewer": body.reviewer}), config)
        return _view(graph, config, body.thread_id)
