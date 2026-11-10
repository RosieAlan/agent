"""知识库上传、文档列表及跨请求检索接口。"""
from contextlib import asynccontextmanager
import logging

from fastapi import APIRouter, HTTPException, UploadFile, Form, Path, Query
from openai import APIError, APITimeoutError
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from repositories.knowledge import list_documents, DocumentNotFound, DocumentConflict
from schemas.knowledge import (
    DocumentIngestResponse, StoredDocument, LibrarySearchInput, LibrarySearchResponse, KnowledgeAnswerResponse,
)
from services.knowledge import MAX_DOCUMENT_BYTES, parse_uploaded_document
from schemas.knowledge import KnowledgeAskInput  # 从定义请求结构的文件导入。
from services.knowledge_library import ingest_document, search_library, update_document, remove_document
from services.knowledge_search import EmbeddingNotConfigured, embedding_model_name
from services.knowledge_answer import answer_question
from services.knowledge_keyword import sync_safely

router = APIRouter(prefix="/knowledge", tags=["knowledge"])
logger = logging.getLogger(__name__)


@asynccontextmanager
async def knowledge_errors():
    # 在统一位置把模型和数据库异常转换为HTTP响应。
    try:
        yield
    except DocumentNotFound as error:
        raise HTTPException(404, detail=str(error)) from error
    except DocumentConflict as error:
        raise HTTPException(409, detail=str(error)) from error
    except EmbeddingNotConfigured as error:
        raise HTTPException(503, detail=str(error)) from error
    except SQLAlchemyError as error:
        logger.warning("知识库数据库操作失败 type=%s", type(error).__name__)
        raise HTTPException(503, detail="知识库数据库暂时不可用，请检查PostgreSQL") from error
    except (TimeoutError, APITimeoutError) as error:
        raise HTTPException(504, detail="知识库模型服务响应超时，请稍后重试") from error
    except APIError as error:
        logger.warning("知识库向量请求失败 status=%s", getattr(error, "status_code", None))
        raise HTTPException(502, detail="知识库模型调用失败，请核对模型、地址、余额与密钥") from error
    except ValueError as error:
        raise HTTPException(502, detail="知识库模型返回格式或来源异常，请核对模型") from error
    except RuntimeError as error:
        raise HTTPException(503, detail=str(error)) from error


@router.get("/documents", response_model=list[StoredDocument])
async def documents():
    async with knowledge_errors():
        return await run_in_threadpool(list_documents, embedding_model_name())


@router.post("/documents", response_model=DocumentIngestResponse)
async def upload_document(file: UploadFile):
    try:
        content = await file.read(MAX_DOCUMENT_BYTES + 1)
        if len(content) > MAX_DOCUMENT_BYTES:
            raise HTTPException(413, detail="文件超过2MiB限制")
        try:
            preview = await run_in_threadpool(parse_uploaded_document, file.filename or "", content)
        except UnicodeDecodeError as error:
            raise HTTPException(422, detail="请使用UTF-8编码的文档") from error
        except ValueError as error:
            raise HTTPException(422, detail=str(error)) from error
        if not 1 <= preview["chunk_count"] <= 100 or len(preview["filename"]) > 255:
            raise HTTPException(422, detail="请使用255字符以内的文件名，文档分块数量需为1至100")
        async with knowledge_errors():
            result = await ingest_document(preview, content)
            result["keyword_synced"] = await run_in_threadpool(sync_safely, result["document_id"])
            return result
    finally:
        await file.close()


@router.post("/search", response_model=LibrarySearchResponse)
async def search(body: LibrarySearchInput):
    async with knowledge_errors():
        return await search_library(body.query, body.document_id)


@router.post("/ask", response_model=KnowledgeAnswerResponse)
async def ask(body: KnowledgeAskInput):
    async with knowledge_errors():
        return await answer_question(
            body.query,        # 当前问题。
            body.document_id,  # 保留原来的文档检索范围。
            [
                message.model_dump()
                for message in body.history
            ],  # 把Pydantic消息对象转为普通字典。
        )


@router.put("/documents/{document_id}", response_model=DocumentIngestResponse)
async def replace_uploaded_document(
    file: UploadFile,
    document_id: str = Path(pattern=r"^[a-f0-9]{64}$"),
    expected_revision: int = Form(ge=1),  # 与文件一起提交页面当前看到的版本。
):
    try:
        content = await file.read(MAX_DOCUMENT_BYTES + 1)
        if len(content) > MAX_DOCUMENT_BYTES:
            raise HTTPException(413, detail="文件超过2MiB限制")
        try:
            preview = await run_in_threadpool(parse_uploaded_document, file.filename or "", content)
        except (UnicodeDecodeError, ValueError) as error:
            raise HTTPException(422, detail="请上传有效的UTF-8 Markdown或TXT文档") from error
        if not 1 <= preview["chunk_count"] <= 100 or len(preview["filename"]) > 255:
            raise HTTPException(422, detail="文件名限255字符，文档分块数量需为1至100")
        async with knowledge_errors():
            result = await update_document(document_id, expected_revision, preview, content)
            result["keyword_synced"] = await run_in_threadpool(sync_safely, document_id)
            return result
    finally:
        await file.close()


@router.delete("/documents/{document_id}")
async def delete_uploaded_document(
    document_id: str = Path(pattern=r"^[a-f0-9]{64}$"),
    expected_revision: int = Query(ge=1),
):
    async with knowledge_errors():
        result = await remove_document(document_id, expected_revision)
        result["keyword_synced"] = await run_in_threadpool(sync_safely, document_id)
        return result
