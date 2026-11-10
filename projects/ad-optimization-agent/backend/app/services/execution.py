"""按依赖执行只读计划，并保留每项任务的结果与状态。"""

from decimal import Decimal
import logging
from time import perf_counter

from sqlalchemy.exc import SQLAlchemyError

from app.repositories.ads import fetch_reports
from app.schemas.planning import TaskPlan
from app.services.ad_metrics import calculate_metrics

logger = logging.getLogger("uvicorn.error")


def _query(task, previous):
    report = fetch_reports(task.args)  # 复用已实现的只读查询。
    if report is None:
        raise ValueError("广告账户不存在，请核对账户编号")
    return {"data_source": "company_test_readonly", **report}


def _sum_known(rows, field):
    values = [row.get(field) for row in rows]
    if any(value is None or value < 0 for value in values):
        return None  # 任一日报缺失该字段时，合计值保持未知。
    return sum(values, Decimal("0"))


def _summarize(report):
    if report.get("has_more") or report.get("offset", 0) != 0:
        raise ValueError("当前为分页片段，请缩小日期或指定活动后再分析；单页最多100条")
    groups = {}
    for row in report["items"]:
        groups.setdefault(row["campaign_id"], []).append(row)
    campaigns = []
    for campaign_id, rows in groups.items():
        totals = {field: _sum_known(rows, field) for field in (
            "spend", "attributed_sales", "clicks", "impressions",
        )}
        totals["attribution_record_present"] = all(row["attribution_record_present"] for row in rows)
        if not totals["attribution_record_present"]:
            totals["attributed_sales"] = None
        campaigns.append({
            "campaign_id": campaign_id,
            "reported_days": len({row["report_date"] for row in rows}),
            **totals, **calculate_metrics(totals),
        })  # 多日指标由总量计算，日报缺失情况单独保留。
    return campaigns


def _filter(task, previous):
    campaigns = _summarize(previous)
    target = task.args.target_roas
    unknown = [item for item in campaigns if item["metrics"]["roas"] is None]
    selected = [item for item in campaigns if item["metrics"]["roas"] is not None
                and item["attributed_sales"] < target * item["spend"]]
    return {
        "data_source": previous["data_source"], "profile": previous["profile"],
        "target_roas": target, "campaign_count": len(campaigns),
        "matched_count": len(selected), "unknown_count": len(unknown),
        "items": selected, "unknown_items": unknown,
    }  # 阈值比较使用原始合计金额，展示值保留四位小数。


def _review(task, previous):
    filtered = "target_roas" in previous
    items = previous["items"] if filtered else _summarize(previous)
    currency = previous["profile"].get("currency") or "币种未知"
    lines = ["广告复盘事实清单", "数据来源：公司历史测试报表（只读）。"]
    if filtered:
        lines.append(f"目标ROAS：{previous['target_roas']}；低于目标：{len(items)}条；"
                     f"数据不足暂无法判断：{previous['unknown_count']}条。")
    else:
        lines.append(f"本次查询返回{len(items)}个广告活动。")
    for item in items[:20]:
        lines.append(f"活动{item['campaign_id']}：花费{item['spend']} {currency}，"
                     f"归因销售额{item['attributed_sales']} {currency}，"
                     f"ROAS={item['metrics']['roas']}，有报表记录{item['reported_days']}天。")
    if len(items) > 20:
        lines.append("正文展示前20条，完整数据见任务结果。")
    lines.append("以上仅说明已有记录的指标，原因分析需补充搜索词、商品转化及变更记录。")
    return {"answer": "\n".join(lines)}  # 本阶段事实报告由代码生成，无外部模型调用。


HANDLERS = {
    "query_reports": _query,
    "find_low_roas": _filter,
    "write_review": _review,
}  # 操作注册表：模型输出的名称对应后端明确提供的函数。


def execute_plan(plan: TaskPlan) -> dict:
    if plan.status == "clarification_required":
        return {"status": "clarification_required", "answer": plan.question,
                "execution_order": [], "tasks": []}
    records = {task.id: {"id": task.id, "action": task.action,
        "status": "pending", "result": None, "error": None} for task in plan.tasks}
    execution_order = []
    for _ in range(len(plan.tasks)):  # 最多执行任务数轮，当前上限为3。
        task = next((task for task in plan.tasks if records[task.id]["status"] == "pending"
            and all(records[dep]["status"] == "completed" for dep in task.depends_on)), None)
        if task is None:
            break
        record = records[task.id]
        record["status"] = "running"
        started = perf_counter()
        execution_order.append(task.id)
        previous = records[task.depends_on[0]]["result"] if task.depends_on else None
        try:
            record["result"] = HANDLERS[task.action](task, previous)
            record["status"] = "completed"
        except SQLAlchemyError as error:
            logger.warning("ad_task_failed task_id=%s error_type=%s", task.id, type(error).__name__)
            record.update(status="failed", error="广告数据源暂时不可用，请稍后重试")
        except ValueError as error:
            record.update(status="failed", error=str(error))
        record["duration_ms"] = round((perf_counter() - started) * 1000, 1)
    for record in records.values():
        if record["status"] == "pending":
            record.update(status="blocked", error="前置任务未完成，本任务等待处理")
    completed = all(record["status"] == "completed" for record in records.values())
    answer = next((record["result"]["answer"] for record in records.values()
        if record["status"] == "completed" and record["action"] == "write_review"),
        "任务执行完成，结果见tasks。" if completed else "部分任务未完成，请查看任务错误信息。")
    return {"status": "completed" if completed else "needs_attention", "answer": answer,
            "execution_order": execution_order, "tasks": list(records.values())}
