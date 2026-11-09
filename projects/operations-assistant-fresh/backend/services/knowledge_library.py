"""上传入库与已存文档检索的业务流程。"""
from hashlib import sha256
from pathlib import Path
from starlette.concurrency import run_in_threadpool
from repositories import knowledge as repository
from services.knowledge_search import embedding_model_name, embed_texts


def validate_dimensions(vectors):
    if any(len(vector) != 1024 for vector in vectors):
        raise RuntimeError("当前知识库要求1024维向量，请核对Embedding模型")


async def ingest_document(preview: dict, original: bytes) -> dict:
    model = embedding_model_name()
    parser_version = ("markdown" if Path(preview["filename"]).suffix.lower() == ".md" else "text") + "-800-120-v1"
    # 内容、切分配置及模型共同决定索引身份，避免不同模型向量混用。
    document_id = sha256(f"{preview['document_id']}|{parser_version}|{model}|1024".encode()).hexdigest()
    existing = await run_in_threadpool(repository.find_document, document_id)
    if existing:
        return {**existing, "status": "indexed", "indexed": True, "reused": True, "total_tokens": 0}
    vectors, tokens = await embed_texts([chunk["content"] for chunk in preview["chunks"]], model)
    validate_dimensions(vectors)
    created = await run_in_threadpool(repository.save_document, document_id, preview, original, model, vectors, parser_version)
    return {"document_id": document_id, "filename": preview["filename"],
            "embedding_model": model, "dimensions": 1024, "chunk_count": len(vectors),
            "status": "indexed", "indexed": True, "reused": not created, "total_tokens": tokens}


async def search_library(query: str, document_id: str | None) -> dict:
    model = embedding_model_name()
    documents = await run_in_threadpool(repository.list_documents, model)
    # 空库和不存在的文档直接返回，节省一次向量请求。
    if document_id:
        selected = await run_in_threadpool(repository.find_document, document_id)
        documents = [selected] if selected and selected["embedding_model"] == model else []
    if not documents:
        return {"query": query, "embedding_model": model, "total_tokens": 0, "matches": []}
    vectors, tokens = await embed_texts([query], model)  # 仅对本轮问题生成向量。
    validate_dimensions(vectors)
    matches = await run_in_threadpool(repository.search_chunks, vectors[0], model, document_id)
    return {"query": query, "embedding_model": model, "total_tokens": tokens, "matches": matches}
