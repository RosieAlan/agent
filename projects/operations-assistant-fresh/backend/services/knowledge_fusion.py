"""合并向量与关键词排名；由两路检索调用方提供同范围、同版本的分块。"""


def fuse_rankings(vector_results: list[dict], keyword_results: list[dict],
                  limit: int = 3, k: int = 60) -> list[dict]:
    """RRF只根据排名计算融合分数，保留原结果并补充两路名次。"""
    if limit < 1 or k < 1:
        raise ValueError("返回数量和排名常数必须为正数")
    merged = {}  # chunk_id相同表示同一分块，最终只返回一份。
    for route, results in (("vector", vector_results), ("keyword", keyword_results)):
        seen = set()  # 同一路内的重复分块只计一次，防止重复加分。
        for rank, item in enumerate(results, 1):
            chunk_id = item["chunk_id"]
            if chunk_id in seen:
                continue
            seen.add(chunk_id)
            if chunk_id not in merged:
                merged[chunk_id] = {**item, "rrf_score": 0.0, "retrieval_ranks": {}}
            merged[chunk_id]["rrf_score"] += 1 / (k + rank)
            merged[chunk_id]["retrieval_ranks"][route] = rank
    # 分数相同时按chunk_id排序，保证同样输入得到稳定结果。
    ranked = sorted(merged.values(), key=lambda item: (-item["rrf_score"], item["chunk_id"]))
    return ranked[:limit]
