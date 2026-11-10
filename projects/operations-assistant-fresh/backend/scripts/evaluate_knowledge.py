"""固定SOP问答评测；运行时请求本地服务，原始结果仅保存到本机。"""
import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter

import httpx

from schemas.knowledge import KnowledgeAnswerResponse


CASES = [
    {
        "name": "采购审批",
        "body": {"query": "采购申请需要谁确认？"},
        "status": "answered", "answer_terms": ["运营主管"],
    },
    {
        "name": "历史追问",
        "body": {
            "query": "那在途的算吗？",
            "history": [
                {"role": "user", "content": "低库存检查用的是可售库存吗？"},
                {"role": "assistant", "content": "低库存检查比较可售数量与检查阈值。"},
            ],
        },
        "status": "answered", "answer_terms": ["到货", "入库", "可售"],
    },
    {
        "name": "缺少自动执行规定",
        "body": {"query": "采购申请提交后，主管超过24小时未回复，是否允许自动执行？"},
        "status": "insufficient_evidence", "answer_terms": [],
    },
    {
        "name": "缺少具体对象",
        "body": {"query": "那个怎么处理？"},
        "status": "clarification_required", "answer_terms": [],
    },
]


def check_response(case: dict, data: dict) -> list[str]:
    """检查可自动核对的规则；答案的完整含义留给人工复核。"""
    problems = []
    if data.get("status") != case["status"]:
        problems.append("业务状态与预期不同")
    for term in case["answer_terms"]:
        if term not in data.get("answer", ""):
            problems.append(f"答案缺少检查词：{term}")
    sources, quotes = data.get("sources", []), data.get("quotes", [])
    if case["status"] == "answered":
        if not sources or not quotes:
            problems.append("缺少来源或原文摘录")
        for quote in quotes:
            text = quote.get("quote", "").strip()
            if not text or not any(text in source["content"] for source in sources):
                problems.append("摘录未出现在返回的来源中")
    elif sources or quotes:
        problems.append("澄清或资料不足时返回了引用")
    if data.get("warnings"):
        problems.append("存在降级或同步告警，请核对warnings")
    return problems


async def main() -> int:
    reports = []
    # 顺序执行4次；使用现有后端的模型配置，HTTP层不自动重试。
    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:8020", timeout=120.0, trust_env=False,
    ) as client:
        for case in CASES:
            started, data, problems = perf_counter(), {}, []
            try:
                response = await client.post("/knowledge/ask", json=case["body"])
                response.raise_for_status()
                data = response.json()
                KnowledgeAnswerResponse.model_validate(data)  # 核对实际响应结构。
                problems = check_response(case, data)
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
                problems.append(f"请求或响应异常：{type(error).__name__}")
                if isinstance(error, httpx.HTTPStatusError):
                    problems.append(f"HTTP {error.response.status_code}")
                    data = {"http_error_body": error.response.text[:2000]}
            report = {
                "case": case["name"], "request": case["body"],
                "expected_status": case["status"], "rules_passed": not problems,
                "duration_seconds": round(perf_counter() - started, 2),
                "problems": problems, "response": data,
                "semantic_review": "待人工核对角色、条件、否定、数字及结论是否忠于原文",
            }
            reports.append(report)
            label = "规则通过" if report["rules_passed"] else "待检查"
            print(f"{case['name']}：{label}，{report['duration_seconds']}秒", flush=True)
            for problem in problems:
                print(f"  - {problem}", flush=True)

    # 本地报告保留原始回答；Git忽略该目录，避免上传业务对话。
    output = Path(__file__).resolve().parents[1] / ".local" / "knowledge-evaluation.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "created_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        "rules_passed": sum(item["rules_passed"] for item in reports),
        "case_count": len(reports),
        "token_statistics_note": "响应包含改写、Embedding和答案Token；当前缺少重排Token，不能据此计算完整费用。",
        "cases": reports,
    }
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"规则检查：{summary['rules_passed']}/{len(reports)}；完整含义需人工复核。")
    print(f"详细结果：{output}")
    return 0 if summary["rules_passed"] == len(reports) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))  # 有失败时返回非零退出码，便于后续CI接入。
