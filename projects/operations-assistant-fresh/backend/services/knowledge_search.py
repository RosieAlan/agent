"""文档内语义检索：使用同一Embedding模型编码问题与分块，返回相关原文。"""
import asyncio
import math
import os

from openai import AsyncOpenAI


class EmbeddingNotConfigured(RuntimeError):
    pass


def cosine_similarity(left: list[float], right: list[float]) -> float:
    # 每个位置的数字相乘再相加，除以两个向量的长度，比较方向相近程度。
    if len(left) != len(right) or not left:
        raise ValueError("向量维度不一致")
    if any(not math.isfinite(value) for value in [*left, *right]):
        raise ValueError("向量包含无效数字")
    left_length, right_length = math.hypot(*left), math.hypot(*right)
    if not left_length or not right_length:
        raise ValueError("模型返回零向量")
    score = math.fsum((a / left_length) * (b / right_length) for a, b in zip(left, right))
    return max(-1.0, min(1.0, score))


async def search_document(preview: dict, query: str) -> dict:
    model_name = os.getenv("EMBEDDING_MODEL", "").strip()
    # 本机选用qwen3.7-text-embedding-flash（默认1024维），通过.env配置。
    # Embedding单独配置，聊天模型继续由core/model.py管理。
    if not model_name:
        raise EmbeddingNotConfigured("请先在backend/.env配置平台支持的EMBEDDING_MODEL")
    if len(preview["chunks"]) > 100:
        raise ValueError("本次预览最多支持100块，请拆分文档后重试")
    texts = [query, *[chunk["content"] for chunk in preview["chunks"]]]
    vectors = []
    total_tokens = 0
    # 当前文本Embedding兼容接口每批最多发10段，关闭SDK自动重试。
    async with AsyncOpenAI(
        api_key=os.getenv("EMBEDDING_API_KEY") or os.environ["OPENAI_API_KEY"],
        base_url=os.getenv("EMBEDDING_BASE_URL") or os.environ["OPENAI_BASE_URL"],
        timeout=20, max_retries=0,
    ) as client:
        async with asyncio.timeout(60):  # 限制整个检索预览的等待时间。
            for start in range(0, len(texts), 10):
                batch = texts[start:start + 10]
                response = await client.embeddings.create(
                    model=model_name, input=batch, encoding_format="float",
                )  # 此处真正请求向量模型，返回每段文字对应的数字列表。
                rows = sorted(response.data, key=lambda row: row.index)
                if [row.index for row in rows] != list(range(len(batch))):
                    raise RuntimeError("向量模型返回数量或编号异常")
                vectors.extend(row.embedding for row in rows)
                if response.usage:
                    total_tokens += response.usage.total_tokens
    matches = [{
        **chunk,
        "score": round(cosine_similarity(vectors[0], vector), 6),
    } for chunk, vector in zip(preview["chunks"], vectors[1:])]
    matches.sort(key=lambda match: match["score"], reverse=True)
    return {
        "status": "retrieved", "indexed": False,
        "filename": preview["filename"], "query": query,
        "embedding_model": model_name, "dimensions": len(vectors[0]),
        "chunk_count": preview["chunk_count"], "total_tokens": total_tokens,
        "matches": matches[:3],
    }
