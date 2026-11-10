"""调用重排模型，保留候选段落的正文和来源信息。"""

import math
import os

import httpx


async def rerank_matches(
    query: str,
    candidates: list[dict],
    top_n: int = 3,
) -> list[dict]:
    # query：用户问题；candidates：混合检索得到的完整段落记录。
    if not candidates:
        return []  # 没有资料时直接返回，节省模型调用。

    url = os.getenv("RERANK_URL", "").strip()
    model = os.getenv("RERANK_MODEL", "").strip()
    if not url or not model:
        raise ValueError("请配置 RERANK_URL 和 RERANK_MODEL")

    count = min(top_n, len(candidates))  # 返回数量最多等于候选数量。
    if count < 1:
        raise ValueError("top_n 必须大于0")

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            url,  # 平台提供的完整重排请求地址。
            headers={
                "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
            },
            json={
                "model": model,  # 重排模型名称。
                "input": {
                    "query": query,  # 用户问题。
                    "documents": [
                        item["content"] for item in candidates
                    ],  # 本次检索得到的候选正文。
                },
                "parameters": {
                    "top_n": count,  # 最终保留几段。
                    "return_documents": False,  # 原文已保存在candidates中。
                },
            },
        )
        response.raise_for_status()  # 401、429、500等进入调用方异常处理。
        payload = response.json()

    output = payload.get("output")
    if not isinstance(output, dict):
        raise ValueError("重排接口缺少output字段")

    rows = output.get("results")  # 这个接口把排序结果放在output.results中。
    if not isinstance(rows, list) or len(rows) != count:
        raise ValueError("重排接口返回的结果数量异常")

    ranked = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("重排结果格式异常")

        index = row.get("index")
        score = row.get("relevance_score")

        # 模型返回的位置必须能找到本次传入的候选段落。
        if type(index) is not int or not 0 <= index < len(candidates):
            raise ValueError("重排接口返回了无效段落位置")
        if index in seen:
            raise ValueError("重排接口返回了重复段落")
        if type(score) not in (int, float) or not math.isfinite(score):
            raise ValueError("重排接口返回了无效分数")

        seen.add(index)
        ranked.append(
            {
                **candidates[index],  # 复制完整记录，保留正文、文件名和来源编号。
                "rerank_score": float(score),  # 新增重排分数。
            }
        )

    ranked.sort(key=lambda item: item["rerank_score"], reverse=True)
    return ranked
