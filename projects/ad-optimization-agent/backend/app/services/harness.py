"""DeepAgents：任务清单、受限业务工具、虚拟报告文件。"""
from uuid import uuid4

from deepagents import create_deep_agent
from deepagents.backends import StateBackend
from deepagents.graph import DeepAgentState
from langchain.agents.middleware import ModelCallLimitMiddleware, TodoListMiddleware
from langchain_core.tools import tool
from langgraph.errors import GraphRecursionError

from app.core.checkpoints import checkpoint_session
from app.core.model import planning_model
from app.repositories.ads import fetch_reports
from app.services.execution import _summarize


class ReviewState(DeepAgentState):
    local_references: dict[str, str]  # 本机检查点字段；Prompt与工具返回均不读取此映射。


def collect_evidence(scope, target):
    report = fetch_reports(scope)  # 原公司数据库仅SELECT；范围来自请求Schema。
    if report is None:
        raise ValueError("广告账户不存在")
    campaigns = _summarize(report)  # 分页片段会被拒绝，避免以局部数据代替完整汇总。
    if len(campaigns) > 5:
        raise ValueError("本节Harness每次最多分析5个活动，请缩小查询范围")
    references = {}
    items = []
    for index, item in enumerate(campaigns, 1):
        alias = f"E{index}"
        references[alias] = item["campaign_id"]  # 真实编号保留在本机，模型只接收E编号。
        items.append({"id": alias, **{key: str(value) if value is not None else None for key, value in {
            "spend": item["spend"], "attributed_sales": item["attributed_sales"],
            "roas": item["metrics"]["roas"],
        }.items()}})
    return {"target_roas": str(target), "items": items}, references


def build_harness(model, evidence_tool, checkpointer=None):
    return create_deep_agent(
        model=model,  # 显式复用qwen3.8-flash；测试时可注入假模型。
        tools=[evidence_tool],
        backend=StateBackend(),  # 文件放在State的files字段；检查点负责存进MySQL。
        state_schema=ReviewState,
        checkpointer=checkpointer,
        middleware=[TodoListMiddleware(), ModelCallLimitMiddleware(run_limit=7, exit_behavior="end")],
        subagents=[{  # 显式限定通用子Agent模型和调用次数；主任务本节自行完成。
            "name": "general-purpose", "description": "仅在确有独立子任务时委派。",
            "model": model, "tools": [],
            "system_prompt": "只根据提供的证据完成子任务；未知原因保持待验证。",
            "middleware": [ModelCallLimitMiddleware(run_limit=2, exit_behavior="end")],
        }],
        system_prompt=(
            "你是广告复盘助手。此次任务由主Agent完成。按以下顺序使用工具："
            "1.write_todos列出查询证据、撰写复盘、检查交付三项任务。"
            "2.get_review_evidence获取证据。3.write_file将中文报告写入/reports/ad-review.md。"
            "4.核对报告与证据，write_todos更新已完成任务，然后简短答复。"
            "每项待办包含content/status；状态使用pending/in_progress/completed。"
            "报告包含证据编号、指标、与目标的差距、待验证原因、下一步检查。"
            "ROAS与目标只能说明达标情况；盈利判断需要毛利和其他费用。"
            "证据为空时如实说明；数据为公司历史测试汇总，只供复盘。"
            "报告控制在600字以内；本任务仅生成报告。"
        ),
    )


def present_result(thread_id, state, references):
    files = {}
    for path, data in state.get("files", {}).items():
        content = data.get("content", "")
        files[path] = "\n".join(content) if isinstance(content, list) else content
    todos = state.get("todos", [])
    calls = [call["name"] for message in state.get("messages", [])
             for call in getattr(message, "tool_calls", [])]
    answers = [message.content for message in state.get("messages", [])
               if getattr(message, "type", "") == "ai" and not getattr(message, "tool_calls", [])]
    complete = (bool(files.get("/reports/ad-review.md")) and bool(todos)
                and all(item.get("status") == "completed" for item in todos)
                and "get_review_evidence" in calls)
    return {"thread_id": thread_id, "status": "completed" if complete else "needs_attention",
            "answer": answers[-1] if answers else "任务尚待检查，请查看清单与文件。",
            "todos": todos, "files": files, "tool_calls": calls,
            "references": state.get("local_references", references)}


def run_harness(body):
    # 先在本机取得最小汇总并检查范围，模型端只收到经授权的四类指标。
    facts, references = collect_evidence(body.scope, body.target_roas)

    @tool
    def get_review_evidence() -> dict:
        """获取本次广告任务的汇总花费、归因销售额、ROAS及目标值；活动用E编号表示。"""
        return facts  # 同一任务重复调用复用本次快照，避免重复SQL。

    thread_id = f"harness:{uuid4()}"
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 60}
    with checkpoint_session(thread_id) as saver:
        graph = build_harness(planning_model(), get_review_evidence, saver)
        try:
            result = graph.invoke({"messages": [{"role": "user", "content": body.goal}],
                                   "local_references": references}, config)
        except GraphRecursionError:
            result = graph.get_state(config).values  # 达到上限仍返回已保存的交付进度。
        return present_result(thread_id, result, references)


def read_harness(thread_id):
    @tool
    def get_review_evidence() -> dict:
        """只读状态入口使用的工具占位定义。"""
        raise RuntimeError("状态查询仅加载检查点")

    with checkpoint_session(thread_id) as saver:
        graph = build_harness(planning_model(), get_review_evidence, saver)
        # get_state合并DeltaChannel增量；直接读底层单个checkpoint会缺少消息和文件。
        saved = graph.get_state({"configurable": {"thread_id": thread_id}})
        if not saved.values:
            return None
        return present_result(thread_id, saved.values, {})
