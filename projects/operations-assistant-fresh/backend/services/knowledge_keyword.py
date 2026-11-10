"""Elasticsearch BM25检索及持久化待办同步；PG保留原始事实。"""
import logging
import os
import re

import httpx
from sqlalchemy import text

from core.knowledge_db import knowledge_engine

logger = logging.getLogger(__name__)
INDEX = "ops-sop-v1"


def search_client():
    return httpx.Client(base_url=os.getenv("ELASTICSEARCH_URL", "http://127.0.0.1:19200"), timeout=5, trust_env=False)


def ensure_index(client):
    response = client.head(f"/{INDEX}")
    if response.status_code != 404:
        response.raise_for_status()
        return
    response = client.put(f"/{INDEX}", json={
        "settings": {"number_of_shards": 1, "number_of_replicas": 0},
        "mappings": {"properties": {
            "document_id": {"type": "keyword"}, "revision": {"type": "integer"},
            "embedding_model": {"type": "keyword"},
            "chunks": {"type": "nested", "properties": {
                "ordinal": {"type": "integer"},
                "content": {"type": "text", "analyzer": "cjk"},
                "identifiers": {"type": "keyword"},
            }},
        }},
    })
    # 另一请求可能已经建好同名索引。
    if response.status_code == 400 and response.json().get("error", {}).get("type") == "resource_already_exists_exception":
        return
    response.raise_for_status()


def sync_pending(document_id: str | None = None, limit: int = 20) -> int:
    """同步有限批次；确认ES成功后才移除对应版本待办。"""
    with knowledge_engine().connect() as conn:
        ids = conn.execute(text("""SELECT document_id FROM knowledge_search_jobs
            WHERE (CAST(:id AS text) IS NULL OR document_id=:id)
            ORDER BY queued_at LIMIT :limit"""), {"id": document_id, "limit": limit}).scalars().all()
    if not ids:
        return 0
    completed = 0
    with search_client() as client:
        ensure_index(client)
        for docid in ids:
            with knowledge_engine().begin() as conn:
                # 同一文档的同步串行执行，避免旧同步覆盖新索引。
                locked = conn.execute(text("SELECT pg_try_advisory_xact_lock(hashtextextended(:id, 0))"), {"id": docid}).scalar()
                if not locked:
                    continue
                job = conn.execute(text("SELECT * FROM knowledge_search_jobs WHERE document_id=:id"), {"id": docid}).mappings().first()
                if not job:
                    continue
                if job["deleted"]:
                    response = client.delete(f"/{INDEX}/_doc/{docid}", params={"refresh": "wait_for"})
                    if response.status_code != 404:
                        response.raise_for_status()
                else:
                    rows = conn.execute(text("""SELECT d.revision, d.embedding_model, c.ordinal, c.content
                        FROM knowledge_documents d JOIN knowledge_chunks c ON c.document_id=d.id
                        WHERE d.id=:id ORDER BY c.ordinal"""), {"id": docid}).mappings().all()
                    if not rows:
                        continue  # 并发删除已生成下一条删除任务。
                    payload = {"document_id": docid, "revision": rows[0]["revision"],
                               "embedding_model": rows[0]["embedding_model"], "chunks": [{
                                   "ordinal": row["ordinal"], "content": row["content"],
                                   "identifiers": re.findall(r"[A-Za-z0-9]+(?:[-_][A-Za-z0-9]+)+", row["content"].upper()),
                               } for row in rows]}
                    response = client.put(f"/{INDEX}/_doc/{docid}", params={"refresh": "wait_for"}, json=payload)
                    response.raise_for_status()
                conn.execute(text("""DELETE FROM knowledge_search_jobs
                    WHERE document_id=:id AND revision=:revision AND deleted=:deleted"""),
                    {"id": docid, "revision": job["revision"], "deleted": job["deleted"]})
                completed += 1
    return completed


def sync_safely(document_id: str | None = None) -> bool:
    try:
        sync_pending(document_id)
        with knowledge_engine().connect() as conn:
            remaining = conn.execute(text("""SELECT EXISTS(SELECT 1 FROM knowledge_search_jobs
                WHERE CAST(:id AS text) IS NULL OR document_id=:id)"""), {"id": document_id}).scalar()
        return not remaining
    except httpx.HTTPError as error:
        logger.warning("关键词索引同步待重试 type=%s", type(error).__name__)
        return False  # 待办仍留在PG，下一次检索或手动同步时重试。


def search_keywords(query: str, model: str, document_id: str | None, limit: int = 10) -> list[dict]:
    filters = [{"term": {"embedding_model": model}}]
    if document_id:
        filters.append({"term": {"document_id": document_id}})
    identifiers = re.findall(r"[A-Za-z0-9]+(?:[-_][A-Za-z0-9]+)+", query.upper())
    should = [{"match": {"chunks.content": query}}]
    if identifiers:
        should.append({"terms": {"chunks.identifiers": identifiers, "boost": 5}})
    with search_client() as client:
        ensure_index(client)
        response = client.post(f"/{INDEX}/_search", json={"size": limit, "query": {"bool": {
            "filter": filters, "must": [{"nested": {"path": "chunks", "query": {"bool": {
                "should": should, "minimum_should_match": 1}}, "inner_hits": {"size": limit}}}],
        }}})
        response.raise_for_status()
        hits = response.json()["hits"]["hits"]
    candidates = []
    for hit in hits:
        for inner in hit["inner_hits"]["chunks"]["hits"]["hits"]:
            candidates.append((hit["_source"]["document_id"], hit["_source"]["revision"],
                               inner["_source"]["ordinal"], inner["_score"]))
    candidates.sort(key=lambda row: (-row[3], row[0], row[2]))
    result = []
    with knowledge_engine().connect() as conn:
        for docid, revision, ordinal, score in candidates:
            # ES只提供候选编号；正文和版本再次从当前PG核对，过滤删除和过期索引。
            row = conn.execute(text("""SELECT c.document_id,c.ordinal,c.content,c.metadata,d.filename,d.revision
                FROM knowledge_chunks c JOIN knowledge_documents d ON d.id=c.document_id
                WHERE d.id=:id AND d.revision=:revision AND d.embedding_model=:model AND c.ordinal=:ordinal"""),
                {"id": docid, "revision": revision, "model": model, "ordinal": ordinal}).mappings().first()
            if row:
                result.append({**dict(row), "chunk_id": f"{docid}:{ordinal}", "score": float(score)})
    return result[:limit]
