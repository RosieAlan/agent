import logging
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from openai import APIError, APITimeoutError

from services.experts import inventory_expert, replenishment_expert
from services.supervisor import select_experts
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


def create_team_graph():
    return (
        StateGraph(TeamState)
        .add_node("supervisor", supervisor_node)
        .add_node("load", load_node)
        .add_node("inventory", inventory_node)
        .add_node("replenishment", replenishment_node)
        .add_node("aggregate", aggregate_node)

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

        .add_edge("aggregate", END)
        .compile()
    )


team_graph = create_team_graph()  # 准备好图，收到请求后才执行。
