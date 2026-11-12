"""读取方案→持久化等待人工确认→记录决定。"""

from datetime import datetime, timezone
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.repositories.proposals import ProposalConflict, decide_proposal, get_proposal
from app.schemas.proposals import ProposalDecision, ProposalView


class ApprovalState(TypedDict, total=False):
    proposal_id: str
    proposal: dict
    prepared_at: str
    decision: dict
    status: str


def prepare(state: ApprovalState):
    proposal = get_proposal(state["proposal_id"])
    if proposal["status"] != "pending_approval":
        raise ProposalConflict("方案已处理，请查看方案当前状态")
    return {
        "proposal": ProposalView.model_validate(proposal).model_dump(mode="json"),
        "prepared_at": datetime.now(timezone.utc).isoformat(), "status": "awaiting_approval",
    }  # 将确认所依据的内容固定在State，后续恢复继续使用该版本。


def approval(state: ApprovalState):
    proposal = state["proposal"]
    decision = interrupt({
        "question": "是否批准这份预算草案？",
        "proposal_id": proposal["id"], "expected_version": proposal["version"],
        "currency": proposal["currency"], "source_budget": proposal["source_budget"],
        "proposed_budget": proposal["proposed_budget"], "reason": proposal["reason"],
    })  # 暂停并返回确认内容；Command(resume=...)传回的值在恢复时从这里返回。
    return {"decision": decision}


def apply_decision(snapshot: dict, decision: dict):
    command = ProposalDecision(
        proposal_id=snapshot["id"], expected_version=snapshot["version"], **decision,
    )
    current = get_proposal(snapshot["id"])
    target = "approved" if command.decision == "approve" else "rejected"
    # 业务事务可能先于图检查点提交；节点重入时核对同版本、同内容及同审批标识的既有结果。
    same_snapshot = all(str(current[key]) == str(snapshot[key]) for key in (
        "profile_id", "campaign_id", "currency", "source_budget", "proposed_budget", "reason",
    ))
    if (same_snapshot and current["status"] == target and current["version"] == command.expected_version + 1
            and current["reviewer"] == command.reviewer):
        return current
    return decide_proposal(command)  # 复用预算快照复核、版本更新与审计事务。


def record(state: ApprovalState):
    result = apply_decision(state["proposal"], state["decision"])
    return {
        "proposal": ProposalView.model_validate(result).model_dump(mode="json"),
        "status": "approved_awaiting_execution" if result["status"] == "approved" else "rejected",
    }


def create_approval_graph(checkpointer):
    return (StateGraph(ApprovalState)
        .add_node("prepare", prepare).add_node("approval", approval).add_node("record", record)
        .add_edge(START, "prepare").add_edge("prepare", "approval")
        .add_edge("approval", "record").add_edge("record", END)
        .compile(checkpointer=checkpointer))
