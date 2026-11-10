"""上传入库与已存文档检索的业务流程。"""

from secrets import token_hex
from sqlalchemy.exc import IntegrityError
import asyncio
import httpx
from starlette.concurrency import run_in_threadpool
from repositories import knowledge as repository
from services.knowledge_search import embedding_model_name, embed_texts
from services.knowledge_fusion import fuse_rankings
from services.knowledge_keyword import sync_safely, search_keywords
from services.knowledge_rerank import rerank_matches  # 新增：段落重排函数。
from services.knowledge import parser_version_for


def validate_dimensions(vectors):
    if any(len(vector) != 1024 for vector in vectors):
        raise RuntimeError("当前知识库要求1024维向量，请核对Embedding模型")


async def ingest_document(preview: dict, original: bytes) -> dict:
    model = embedding_model_name()
    # 用户直接上传；后端用文件名找到已有文档，再复用版本检查和事务更新。
    named = await run_in_threadpool(
        repository.find_by_filename, preview["filename"], model
    )
    if named:
        return await update_document(
            named["document_id"], named["revision"], preview, original
        )
    parser_version = parser_version_for(preview["filename"])
    # 内容、切分配置及模型共同决定索引身份，避免不同模型向量混用。
    document_id = token_hex(32)  # 文档编号保持稳定，内容更新后仍使用这个编号。
    existing = await run_in_threadpool(
        repository.find_identity, preview["document_id"], parser_version, model
    )
    if existing:
        return {
            **existing,
            "status": "indexed",
            "indexed": True,
            "reused": True,
            "total_tokens": 0,
        }
    vectors, tokens = await embed_texts(
        [chunk["content"] for chunk in preview["chunks"]], model
    )
    validate_dimensions(vectors)
    created = await run_in_threadpool(
        repository.save_document,
        document_id,
        preview,
        original,
        model,
        vectors,
        parser_version,
    )
    if not created:
        existing = await run_in_threadpool(
            repository.find_identity, preview["document_id"], parser_version, model
        )
        if existing is None:
            raise repository.DocumentConflict("同名文档正在被保存，请重新上传")
        return {
            **existing,
            "status": "indexed",
            "indexed": True,
            "reused": True,
            "total_tokens": tokens,
        }
    return {
        "document_id": document_id,
        "filename": preview["filename"],
        "embedding_model": model,
        "dimensions": 1024,
        "chunk_count": len(vectors),
        "status": "indexed",
        "indexed": True,
        "reused": False,
        "total_tokens": tokens,
        "revision": 1,
    }


async def current_document(document_id, expected_revision):
    model = embedding_model_name()
    existing = await run_in_threadpool(repository.find_document, document_id)
    if not existing or existing["embedding_model"] != model:
        raise repository.DocumentNotFound("文档不存在，请刷新列表")
    if existing["revision"] != expected_revision:
        raise repository.DocumentConflict("文档已被更新，请刷新列表后重试")
    return existing


async def update_document(document_id, expected_revision, preview, original):
    existing = await current_document(document_id, expected_revision)
    model = existing["embedding_model"]
    parser = parser_version_for(preview["filename"])
    duplicate = await run_in_threadpool(
        repository.find_identity, preview["document_id"], parser, model
    )
    if duplicate:
        if duplicate["document_id"] != document_id:
            raise repository.DocumentConflict(
                "相同内容已保存为另一份文档，请选择该文档"
            )
        return {
            **existing,
            "status": "indexed",
            "indexed": True,
            "reused": True,
            "total_tokens": 0,
        }
    vectors, tokens = await embed_texts(
        [chunk["content"] for chunk in preview["chunks"]], model
    )
    validate_dimensions(vectors)
    try:
        revision = await run_in_threadpool(
            repository.replace_document,
            document_id,
            expected_revision,
            preview,
            original,
            model,
            vectors,
            parser,
        )
    except IntegrityError as error:
        raise repository.DocumentConflict("相同内容已被保存，请刷新列表") from error
    return {
        "document_id": document_id,
        "filename": preview["filename"],
        "embedding_model": model,
        "dimensions": 1024,
        "chunk_count": len(vectors),
        "revision": revision,
        "status": "indexed",
        "indexed": True,
        "reused": False,
        "total_tokens": tokens,
    }


async def remove_document(document_id, expected_revision):
    existing = await current_document(document_id, expected_revision)
    return await run_in_threadpool(
        repository.delete_document,
        document_id,
        expected_revision,
        existing["embedding_model"],
    )


async def search_library(query: str, document_id: str | None) -> dict:
    model = embedding_model_name()
    documents = await run_in_threadpool(repository.list_documents, model)
    # 空库和不存在的文档直接返回，节省一次向量请求。
    if document_id:
        selected = await run_in_threadpool(repository.find_document, document_id)
        documents = (
            [selected] if selected and selected["embedding_model"] == model else []
        )
    if not documents:
        return {
            "query": query,
            "embedding_model": model,
            "total_tokens": 0,
            "matches": [],
        }
    vectors, tokens = await embed_texts([query], model)  # 仅对本轮问题生成向量。
    validate_dimensions(vectors)

    def keyword_route():
        synced = sync_safely()
        return search_keywords(query, model, document_id), synced

    # 两路先各取10个候选；融合后保留3段供回答使用。
    vector_results, keyword_result = await asyncio.gather(
        run_in_threadpool(repository.search_chunks, vectors[0], model, document_id, 10),
        run_in_threadpool(keyword_route),
        return_exceptions=True,
    )
    if isinstance(vector_results, BaseException):
        raise vector_results
    warnings = []
    mode = "hybrid"
    if isinstance(keyword_result, httpx.HTTPError):
        keyword_results = []
        mode = "vector"
        warnings.append("关键词服务暂时不可用，本次使用向量检索；同步待办已保留。")
    elif isinstance(keyword_result, BaseException):
        raise keyword_result
    else:
        keyword_results, synced = keyword_result
        if not synced:
            warnings.append("部分关键词索引等待同步，当前结果已过滤过期版本。")
    vector_results, keyword_results = await run_in_threadpool(
        repository.current_candidates, vector_results, keyword_results
    )
    # 修改：先保留10段，让重排模型有更多候选可选。
    candidates = fuse_rankings(vector_results, keyword_results, limit=10)

    # 默认准备好RRF前3段，重排服务失败时使用。
    matches = candidates[:3]

    if candidates:
        try:
            # 新增：真正调用重排模型，返回重新排序后的前3段。
            matches = await rerank_matches(query, candidates, top_n=3)
        except (httpx.HTTPError, ValueError) as error:
            # 超时、HTTP失败或返回格式异常时，保留已有检索结果。
            warnings.append(
                f"重排暂时不可用，本次采用RRF排序。错误类型：{type(error).__name__}"
            )

    return {
        "query": query,
        "embedding_model": model,
        "total_tokens": tokens,  # 这个字段目前仍只统计Embedding Token。
        "matches": matches,
        "retrieval_mode": mode,
        "warnings": warnings,
    }
