"""文档和分块的持久化查询；所有外部值使用绑定参数。"""
import json
from sqlalchemy import text
from core.knowledge_db import knowledge_engine


def list_documents(model_name: str) -> list[dict]:
    with knowledge_engine().connect() as conn:
        rows = conn.execute(text("""
            SELECT id AS document_id, filename, embedding_model, dimensions, chunk_count, created_at
            FROM knowledge_documents WHERE embedding_model=:model
            ORDER BY created_at DESC LIMIT 100
        """), {"model": model_name}).mappings()
        return [dict(row) for row in rows]


def find_document(document_id: str):
    with knowledge_engine().connect() as conn:
        row = conn.execute(text("""
            SELECT id AS document_id, filename, embedding_model, dimensions, chunk_count
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
            ON CONFLICT (id) DO NOTHING RETURNING id
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


def search_chunks(vector: list[float], model_name: str, document_id: str | None) -> list[dict]:
    with knowledge_engine().connect() as conn:
        rows = conn.execute(text("""
            SELECT c.document_id, c.ordinal, c.content, c.metadata, d.filename,
                   1 - (c.embedding <=> CAST(:vector AS vector)) AS score
            FROM knowledge_chunks c JOIN knowledge_documents d ON d.id=c.document_id
            WHERE d.embedding_model=:model
              AND (CAST(:document_id AS text) IS NULL OR d.id=:document_id)
            ORDER BY c.embedding <=> CAST(:vector AS vector), c.document_id, c.ordinal
            LIMIT 3
        """), {"vector": json.dumps(vector), "model": model_name,
               "document_id": document_id}).mappings()
        return [{**dict(row), "chunk_id": f"{row['document_id']}:{row['ordinal']}"} for row in rows]
