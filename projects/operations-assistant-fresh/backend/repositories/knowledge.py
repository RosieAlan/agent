"""文档和分块的持久化查询；所有外部值使用绑定参数。"""
import json
from sqlalchemy import text
from core.knowledge_db import knowledge_engine


class DocumentNotFound(RuntimeError):
    pass


class DocumentConflict(RuntimeError):
    pass


def insert_chunks(conn, document_id, preview, vectors):
    # 父块与子块在同一事务内写入，文档更新失败时整体回滚。
    parents = preview.get("parents", [])
    if parents:
        conn.execute(text("""INSERT INTO knowledge_parents(document_id,parent_id,content)
            VALUES (:document_id,:parent_id,:content)"""),
            [{**parent, "document_id": document_id} for parent in parents])
    rows = [{"id": document_id, "ordinal": index, "content": chunk["content"],
             "metadata": json.dumps({**chunk["metadata"], "document_id": document_id}, ensure_ascii=False),
             "embedding": json.dumps(vector)}
            for index, (chunk, vector) in enumerate(zip(preview["chunks"], vectors), 1)]
    conn.execute(text("""
        INSERT INTO knowledge_chunks (document_id, ordinal, content, metadata, embedding)
        VALUES (:id, :ordinal, :content, CAST(:metadata AS jsonb), CAST(:embedding AS vector))
    """), rows)


def find_identity(content_hash, parser_version, model):
    with knowledge_engine().connect() as conn:
        row = conn.execute(text("""SELECT id AS document_id, filename, embedding_model,
                dimensions, chunk_count, revision, content_hash, parser_version
            FROM knowledge_documents
            WHERE content_hash=:hash AND parser_version=:parser AND embedding_model=:model
              AND dimensions=1024"""), {"hash": content_hash, "parser": parser_version, "model": model}).mappings().first()
        return dict(row) if row else None


def find_by_filename(filename, model):
    with knowledge_engine().connect() as conn:
        row = conn.execute(text("""SELECT id AS document_id, revision
            FROM knowledge_documents WHERE filename=:filename AND embedding_model=:model"""),
            {"filename": filename, "model": model}).mappings().first()
        return dict(row) if row else None


def list_documents(model_name: str) -> list[dict]:
    with knowledge_engine().connect() as conn:
        rows = conn.execute(text("""
            SELECT id AS document_id, filename, embedding_model, dimensions, chunk_count, created_at, revision
            FROM knowledge_documents WHERE embedding_model=:model
            ORDER BY created_at DESC LIMIT 100
        """), {"model": model_name}).mappings()
        return [dict(row) for row in rows]


def find_document(document_id: str):
    with knowledge_engine().connect() as conn:
        row = conn.execute(text("""
            SELECT id AS document_id, filename, embedding_model, dimensions, chunk_count, revision, content_hash, parser_version
            FROM knowledge_documents WHERE id=:id
        """), {"id": document_id}).mappings().first()
        return dict(row) if row else None


def save_document(document_id: str, preview: dict, original: bytes,
                  model_name: str, vectors: list[list[float]], parser_version: str) -> bool:
    # 一份文档及其全部分块在同一事务中保存，整体成功或整体回滚。
    with knowledge_engine().begin() as conn:
        inserted = conn.execute(text("""
            INSERT INTO knowledge_documents
                (id, content_hash, filename, original_content, parser_version, embedding_model, dimensions, chunk_count)
            VALUES (:id, :hash, :filename, :original, :parser, :model, 1024, :count)
            ON CONFLICT DO NOTHING RETURNING id
        """), {"id": document_id, "hash": preview["document_id"],
               "filename": preview["filename"], "original": original,
               "model": model_name, "parser": parser_version, "count": len(vectors)}).scalar_one_or_none()
        if inserted is None:
            return False  # 并发重复上传复用已提交的文档。
        insert_chunks(conn, document_id, preview, vectors)
    return True


def replace_document(document_id, expected_revision, preview, original, model, vectors, parser):
    # 修改原文、替换分块和向量共用一次事务，失败时保留原文档。
    with knowledge_engine().begin() as conn:
        revision = conn.execute(text("""UPDATE knowledge_documents
            SET content_hash=:hash, filename=:filename, original_content=:original,
                parser_version=:parser, chunk_count=:count, revision=revision+1
            WHERE id=:id AND revision=:revision AND embedding_model=:model
            RETURNING revision"""), {"id": document_id, "revision": expected_revision,
                "hash": preview["document_id"], "filename": preview["filename"],
                "original": original, "parser": parser, "count": len(vectors), "model": model}).scalar_one_or_none()
        if revision is None:
            raise DocumentConflict("文档已被更新或删除，请刷新列表后重试")
        conn.execute(text("DELETE FROM knowledge_chunks WHERE document_id=:id"), {"id": document_id})
        conn.execute(text("DELETE FROM knowledge_parents WHERE document_id=:id"), {"id": document_id})
        insert_chunks(conn, document_id, preview, vectors)
    return revision


def delete_document(document_id, expected_revision, model):
    with knowledge_engine().begin() as conn:
        count = conn.execute(text("""DELETE FROM knowledge_documents
            WHERE id=:id AND revision=:revision AND embedding_model=:model
            RETURNING chunk_count"""), {"id": document_id, "revision": expected_revision,
                "model": model}).scalar_one_or_none()
        if count is None:
            raise DocumentConflict("文档已被更新或删除，请刷新列表后重试")
        # 外键 ON DELETE CASCADE 同步删除该文档的所有分块和向量。
    return {"document_id": document_id, "deleted": True, "deleted_chunks": count}


def search_chunks(vector: list[float], model_name: str, document_id: str | None, limit: int = 3) -> list[dict]:
    with knowledge_engine().connect() as conn:
        rows = conn.execute(text("""
            SELECT c.document_id, c.ordinal, c.content, c.metadata, d.filename, d.revision,
                   1 - (c.embedding <=> CAST(:vector AS vector)) AS score
            FROM knowledge_chunks c JOIN knowledge_documents d ON d.id=c.document_id
            WHERE d.embedding_model=:model
              AND (CAST(:document_id AS text) IS NULL OR d.id=:document_id)
            ORDER BY c.embedding <=> CAST(:vector AS vector), c.document_id, c.ordinal
            LIMIT :limit
        """), {"vector": json.dumps(vector), "model": model_name,
               "document_id": document_id, "limit": limit}).mappings()
        return [{**dict(row), "chunk_id": f"{row['document_id']}:{row['ordinal']}"} for row in rows]


def current_candidates(vector_results, keyword_results):
    ids = list({item["document_id"] for item in [*vector_results, *keyword_results]})
    if not ids:
        return [], []
    with knowledge_engine().connect() as conn:
        revisions = dict(conn.execute(text("SELECT id,revision FROM knowledge_documents WHERE id=ANY(:ids)"), {"ids": ids}).all())
    return ([item for item in vector_results if revisions.get(item["document_id"]) == item["revision"]],
            [item for item in keyword_results if revisions.get(item["document_id"]) == item["revision"]])


def answer_context(matches: list[dict]) -> list[dict]:
    """按当前版本回取父块；旧文档沿用原子块，同父块合并为一份来源。"""
    matches = matches[:3]  # 调用方与数据库层同时限制本次回答的来源数量。
    if not matches:
        return []
    hits = [{"document_id": item["document_id"], "ordinal": item["ordinal"],
             "revision": item["revision"]} for item in matches]
    with knowledge_engine().connect() as conn:
        rows = conn.execute(text("""
            SELECT c.document_id,c.ordinal,d.revision,c.content,c.metadata,
                   p.content AS parent_content
            FROM jsonb_to_recordset(CAST(:hits AS jsonb))
                 AS h(document_id text, ordinal integer, revision integer)
            JOIN knowledge_documents d ON d.id=h.document_id AND d.revision=h.revision
            JOIN knowledge_chunks c ON c.document_id=d.id AND c.ordinal=h.ordinal
            LEFT JOIN knowledge_parents p ON p.document_id=c.document_id
                 AND p.parent_id=c.metadata->>'parent_id'
        """), {"hits": json.dumps(hits)}).mappings().all()
    current = {(row["document_id"], row["ordinal"], row["revision"]): row for row in rows}
    contexts = {}
    for match in matches:  # 保留重排顺序，最多3个父块、共7200字符。
        row = current.get((match["document_id"], match["ordinal"], match["revision"]))
        if row is None:
            continue  # 已更新或删除的命中从本轮回答中移除。
        parent_id = row["metadata"].get("parent_id")
        if parent_id and row["parent_content"] is None:
            raise RuntimeError("文档父块缺失，请重新上传文档建立索引")
        key = (match["document_id"], match["revision"], parent_id or match["chunk_id"])
        if key in contexts:
            contexts[key]["matched_child_ids"].append(match["chunk_id"])
            continue
        contexts[key] = {
            **match, "content": row["parent_content"] or row["content"],
            "metadata": dict(row["metadata"]),
            "context_type": "parent" if parent_id else "chunk",
            "matched_child_ids": [match["chunk_id"]],
        }
    return list(contexts.values())
