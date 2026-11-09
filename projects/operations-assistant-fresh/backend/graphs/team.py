import asyncio
import logging
import time
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from openai import APIError, APITimeoutError
from pydantic import ValidationError

from services.experts import inventory_expert, replenishment_expert
from services.supervisor import select_experts
from services.team_review import review_team_report, refine_team_report
from tools.inventory import check_inventory

logger = logging.getLogger(__name__)


class TeamState(TypedDict):
    input: str                  # 用户问题。
    sku: str                    # 本次查询的商品编号。
    threshold: int              # 本次低库存阈值。
    experts: list[str]          # Supervisor选中的专家。
    reason: str                 # 选择理由。
    facts: dict                 # 查到的库存事实。
    inventory_report: str       # 库存专家的结果。
    replenishment_report: str   # 补货专家的结果。
    inventory_error: str        # 每位专家单独写错误，避免并行写入冲突。
    replenishment_error: str
    expert_errors: dict[str, str]  # 汇总节点整理给前端的失败信息。
    status: str                 # 最终处理状态。
    answer: str                 # 汇总后的答复。
    deadline: float             # HTTP入口传入整次请求的结束时间。
    quality_status: str
    review_issues: list[str]
    revise_count: int


async def supervisor_node(state: TeamState) -> dict:
    # 调用上一块已经验证过的专家选择函数。
    plan = await select_experts(state["input"])

    return {
        "experts": plan.experts,
        "reason": plan.reason,
        "inventory_report": "",       # 本次请求从空结果开始。
        "replenishment_report": "",
        "inventory_error": "",
        "replenishment_error": "",
        "expert_errors": {},
        "quality_status": "skipped",
        "review_issues": [],
        "revise_count": 0,
        "status": "completed" if plan.experts else "needs_clarification",
        "answer": "" if plan.experts else plan.reason,
    }


def after_supervisor(state: TeamState) -> str:
    # 有专家参与就查询库存；空名单直接结束并返回原因。
    return "load" if state["experts"] else END


async def load_node(state: TeamState) -> dict:
    # 后端明确执行库存工具，得到一份供专家共同使用的数据。
    facts = await check_inventory.ainvoke({
        "sku": state["sku"],
        "threshold": state["threshold"],
    })

    if not facts["items"]:
        return {
            "facts": facts,
            "status": "not_found",
            "answer": "未找到该商品的库存记录。",
        }

    return {"facts": facts}  # 将查询结果写进State。


def selected_experts(state: TeamState) -> list[str] | str:
    # 查到数据时返回专家名单，名单中的节点并行执行。
    return state["experts"] if state["facts"]["items"] else END


async def inventory_node(state: TeamState) -> dict:
    try:
        report = await inventory_expert(state["input"], state["facts"])
        return {"inventory_report": report, "inventory_error": ""}
    except (TimeoutError, APITimeoutError):
        logger.exception("库存专家超时")
        return {"inventory_report": "", "inventory_error": "库存分析超时，请稍后重试"}
    except (APIError, RuntimeError):
        logger.exception("库存专家分析失败")
        return {"inventory_report": "", "inventory_error": "库存分析暂时失败，请稍后重试"}


async def replenishment_node(state: TeamState) -> dict:
    try:
        report = await replenishment_expert(state["input"], state["facts"])
        return {"replenishment_report": report, "replenishment_error": ""}
    except (TimeoutError, APITimeoutError):
        logger.exception("补货专家超时")
        return {"replenishment_report": "", "replenishment_error": "补货分析超时，请稍后重试"}
    except (APIError, RuntimeError):
        logger.exception("补货专家分析失败")
        return {"replenishment_report": "", "replenishment_error": "补货分析暂时失败，请稍后重试"}


def aggregate_node(state: TeamState) -> dict:
    sections = []

    errors = {}
    titles = {"inventory": "库存分析", "replenishment": "补货建议"}
    for name in state["experts"]:
        error = state[f"{name}_error"]  # 例如读取 replenishment_error。
        if error:
            errors[name] = error
        else:
            sections.append(f"## {titles[name]}\n" + state[f"{name}_report"])

    if not sections:  # 所选专家全部失败，交给HTTP入口返回502。
        raise RuntimeError("所选专家均未完成分析")
    if errors:
        sections.append("## 未完成的部分\n" + "\n".join(errors.values()))

    return {
        "answer": "\n\n".join(sections),  # 保留成功报告，附上缺失部分。
        "status": "partial_success" if errors else "completed",
        "expert_errors": errors,
    }


async def quality_node(state: TeamState) -> dict:
    answer = state["answer"]  # 随时保留上一份完整报告，失败时仍可返回。
    count = 0
    issues = []
    # 评审和修订总共最多12秒；给HTTP序列化保留0.2秒。
    budget = min(12.0, state.get("deadline", float("inf")) - time.monotonic() - 0.2)
    try:
        if budget <= 0:
            raise TimeoutError("评审可用时间耗尽")
        async with asyncio.timeout(budget):
            while True:
                review = await review_team_report(
                    state["input"], state["facts"], answer, state["expert_errors"],
                )
                issues = review["issues"]
                if review["passed"] and not issues:
                    return {"answer": answer, "quality_status": "passed",
                            "review_issues": [], "revise_count": count}
                if not issues:
                    issues = ["评审未通过，具体问题需要人工核对"]
                if count >= 2:  # 最多两次修订、三次评审。
                    break
                answer = await refine_team_report(
                    state["facts"], answer, issues, state["expert_errors"],
                )
                count += 1
                # 用程序保留失败披露，确保修订后仍能看到缺失部分。
                missing = [error for error in state["expert_errors"].values() if error not in answer]
                if missing:
                    answer += "\n\n## 未完成的部分\n" + "\n".join(missing)
    except (TimeoutError, APITimeoutError, APIError, RuntimeError, ValidationError):
        logger.exception("报告评审或修订未完成，保留已有报告")
        issues = ["自动评审或修订未完成，请人工核对报告"]
    return {"answer": answer, "quality_status": "needs_review",
            "review_issues": issues, "revise_count": count}


def create_team_graph():
    return (
        StateGraph(TeamState)
        .add_node("supervisor", supervisor_node)
        .add_node("load", load_node)
        .add_node("inventory", inventory_node)
        .add_node("replenishment", replenishment_node)
        .add_node("aggregate", aggregate_node)
        .add_node("quality", quality_node)

        .add_edge(START, "supervisor")

        .add_conditional_edges(
            "supervisor",
            after_supervisor,
            {"load": "load", END: END},
        )

        .add_conditional_edges(
            "load",
            selected_experts,
            {
                "inventory": "inventory",
                "replenishment": "replenishment",
                END: END,
            },
        )

        # 当前专家都在同一层，完成后进入同一个汇总节点。
        .add_edge("inventory", "aggregate")
        .add_edge("replenishment", "aggregate")

        .add_edge("aggregate", "quality")  # 汇总后统一检查，专家报告保留原文。
        .add_edge("quality", END)
        .compile()
    )


team_graph = create_team_graph()  # 准备好图，收到请求后才执行。
