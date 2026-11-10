"""运行固定库存/路由题集；保存报告，任一失败或错误时返回退出码1。"""

import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from uuid import uuid4

from langchain_core.callbacks.usage import get_usage_metadata_callback

from services.inventory import inspect_inventory
from services.supervisor import select_experts  # 读取已有模型与.env配置。
from core.tracing import tracing_client


def grade(case: dict, result: dict) -> bool:
    """比较明确业务字段；专家名单按集合顺序无关方式比较。"""
    if case["kind"] == "routing":
        actual = {"experts": sorted(result["experts"])}
        expected = {"experts": sorted(case["expected"]["experts"])}
    else:
        actual = {
            "low_stock_count": result["low_stock_count"],
            "available_by_store": {row["store_code"]: row["available"] for row in result["items"]},
        }
        expected = case["expected"]
    return actual == expected  # 结果不符时，当前题判为失败。


async def run_case(case: dict) -> dict:
    started = time.monotonic()
    row = {"id": case["id"], "kind": case["kind"], "expected": case["expected"]}
    usage = None
    try:
        async with asyncio.timeout(35):  # 单题等待上限；模型自身仍保留原来的超时配置。
            if case["kind"] == "inventory":
                result = await asyncio.to_thread(
                    inspect_inventory, case["sku"], case["threshold"], fresh=True,
                )  # 直接查询MySQL，固定检查当前数据库样例。
            elif case["kind"] == "routing":
                with get_usage_metadata_callback() as usage:
                    result = (await select_experts(case["input"])).model_dump()
                # callback读取真实供应商统计，同时兼容结构化输出调用。
            else:
                raise ValueError("unsupported_case_kind")
        row.update(status="passed" if grade(case, result) else "failed", actual=result)
    except Exception as error:
        row.update(status="error", error_type=type(error).__name__)  # 题目执行出错单独计数。
    row["duration_ms"] = round((time.monotonic() - started) * 1000, 2)
    totals = [value["total_tokens"] for value in usage.usage_metadata.values()] if usage else []
    row["tokens"] = sum(totals) if totals else (0 if case["kind"] == "inventory" else None)
    return row  # 模型统计缺失记为null；库存规则检查无需模型Token。


def summarize(rows: list[dict]) -> dict:
    passed = sum(row["status"] == "passed" for row in rows)
    return {
        "total": len(rows),
        "passed": passed,
        "failed": sum(row["status"] == "failed" for row in rows),
        "errors": sum(row["status"] == "error" for row in rows),
        "gate_passed": bool(rows) and passed == len(rows),  # 本批题要求全部通过。
        "reported_tokens": sum(row["tokens"] or 0 for row in rows),
        "usage_missing_cases": [row.get("id") for row in rows if row["tokens"] is None],
    }


async def main() -> int:
    backend_dir = Path(__file__).resolve().parents[1]
    dataset = json.loads((backend_dir / "evaluation" / "operations-v1.json").read_text(encoding="utf-8"))
    started = time.monotonic()
    rows = []
    for case in dataset["cases"]:
        row = await run_case(case)  # 顺序执行，避免评测时额外挤占模型并发额度。
        rows.append(row)
        print(f"{row['status']:6} {row['id']} | {row['duration_ms']}ms | Token={row['tokens']}")
    report = {
        "dataset_version": dataset["version"],
        "data_source": dataset["data_source"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model": os.environ["OPENAI_MODEL"],
        "duration_ms": round((time.monotonic() - started) * 1000, 2),
        **summarize(rows),
        "cases": rows,
    }
    output_dir = backend_dir / ".local" / "evaluations"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"operations-{uuid4().hex}.json"  # 每次留独立报告，供修改前后对照。
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"通过 {report['passed']}/{report['total']}；已报告Token {report['reported_tokens']}")
    print("报告：", output)
    return 0 if report["gate_passed"] else 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
    finally:
        client = tracing_client()
        if client is not None:
            client.shutdown()  # 脚本退出前上报本轮专家选择记录。
    raise SystemExit(exit_code)
