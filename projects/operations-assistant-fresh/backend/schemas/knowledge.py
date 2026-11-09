from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, field_validator  # 校验接口输入和返回字段。


class KnowledgeChunk(BaseModel):
    chunk_id: str
    content: str
    metadata: dict[str, str]


class DocumentPreview(BaseModel):
    status: str
    indexed: bool  # 当前解析完成；向量入库后再更新索引状态。
    document_id: str
    filename: str
    size_bytes: int
    character_count: int
    chunk_count: int
    chunks: list[KnowledgeChunk]


class SearchMatch(KnowledgeChunk):
    score: float  # 余弦相似度，用于排序；事实正确性仍需核对原文。


class DocumentSearchResponse(BaseModel):
    status: str
    indexed: bool
    filename: str
    query: str
    embedding_model: str
    dimensions: int
    chunk_count: int
    total_tokens: int
    matches: list[SearchMatch]


class StoredDocument(BaseModel):
    revision: int
    document_id: str
    filename: str
    embedding_model: str
    dimensions: int
    chunk_count: int
    created_at: datetime


class DocumentIngestResponse(BaseModel):
    revision: int
    document_id: str
    filename: str
    embedding_model: str
    dimensions: int
    chunk_count: int
    status: str
    indexed: bool
    reused: bool
    total_tokens: int


class LibrarySearchInput(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    document_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")

    @field_validator("query")
    @classmethod
    def query_has_text(cls, value):
        if not value.strip():
            raise ValueError("请输入要检索的问题")
        return value.strip()


class StoredSearchMatch(SearchMatch):
    document_id: str
    filename: str


class LibrarySearchResponse(BaseModel):
    query: str
    embedding_model: str
    total_tokens: int
    matches: list[StoredSearchMatch]


class EvidenceAnswer(BaseModel):
    """约束聊天模型的输出；来源编号由后端提供。"""
    answerable: bool = Field(description="提供的段落是否足以回答问题")
    answer: str = Field(min_length=1, max_length=4000, description="根据段落给出的简洁答案；缺资料时说明缺口")
    source_ids: list[int] = Field(max_length=3, description="支持答案的段落编号，例如[1,2]；资料不足返回空列表")


class KnowledgeAnswerResponse(BaseModel):
    status: Literal["answered", "insufficient_evidence"]
    answer: str
    sources: list[StoredSearchMatch]
    embedding_tokens: int
    chat_tokens: int
