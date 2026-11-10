"""文档和分块的持久化查询；所有外部值使用绑定参数。"""
import json
from sqlalchemy import text
from core.knowledge_db import knowledge_engine


class DocumentNotFound(RuntimeError):
    pass


class DocumentConflict(RuntimeError):
    pass


def insert_chunks(conn, document_id, preview, vectors):
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
        rows = [{"id": document_id, "ordinal": index,
                 "content": chunk["content"],
                 "metadata": json.dumps({**chunk["metadata"], "document_id": document_id}, ensure_ascii=False),
                 "embedding": json.dumps(vector)}
                for index, (chunk, vector) in enumerate(zip(preview["chunks"], vectors), 1)]
        conn.execute(text("""
            INSERT INTO knowledge_chunks (document_id, ordinal, content, metadata, embedding)
            VALUES (:id, :ordinal, :content, CAST(:metadata AS jsonb), CAST(:embedding AS vector))
        """), rows)
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
