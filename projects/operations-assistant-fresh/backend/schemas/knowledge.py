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
    keyword_synced: bool = False
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


class HistoryMessage(BaseModel):
    """一条历史消息。"""

    role: Literal["user", "assistant"]  # 限定为用户或助手消息。
    content: str = Field(
        min_length=1,
        max_length=2000,
    )  # 限制单条历史长度。


class KnowledgeAskInput(LibrarySearchInput):
    """沿用query、document_id，再增加历史消息。"""

    history: list[HistoryMessage] = Field(
        default_factory=list,
        max_length=8,
    )  # 本次最多接收8条历史；省略时使用空列表。


class StoredSearchMatch(SearchMatch):
    rrf_score: float | None = None
    retrieval_ranks: dict[str, int] = Field(default_factory=dict)
    document_id: str
    filename: str
    rerank_score: float | None = None  # 重排成功时有分数；降级时为空。


class LibrarySearchResponse(BaseModel):
    retrieval_mode: Literal["vector", "hybrid"] = "vector"
    warnings: list[str] = Field(default_factory=list)
    query: str
    embedding_model: str
    total_tokens: int
    matches: list[StoredSearchMatch]


class EvidenceQuote(BaseModel):
    """一条从本次参考段落连续复制的原文摘录。"""

    source_id: int = Field(ge=1)  # 对应本次提供的段落编号。
    quote: str = Field(min_length=1, max_length=1000, description="从对应段落连续复制的原文，保留原字句和标点")


class EvidenceAnswer(BaseModel):
    """约束聊天模型的输出；来源编号由后端提供。"""

    answerable: bool = Field(description="提供的段落是否足以回答问题")
    answer: str = Field(
        min_length=1,
        max_length=4000,
        description="根据段落给出的简洁答案；缺资料时说明缺口",
    )
    source_ids: list[int] = Field(
        max_length=3, description="支持答案的段落编号，例如[1,2]；资料不足返回空列表"
    )
    quotes: list[EvidenceQuote] = Field(
        max_length=3, description="每个引用来源至少提供一条支持答案的原文摘录；资料不足时返回空列表"
    )


class KnowledgeAnswerResponse(BaseModel):
    retrieval_mode: Literal["vector", "hybrid"] = "vector"
    warnings: list[str] = Field(default_factory=list)
    # status: Literal["answered", "insufficient_evidence"]
    status: Literal[
        "answered",
        "insufficient_evidence",
        "clarification_required",
    ]  # 新增：问题意思需要用户补充。
    answer: str
    sources: list[StoredSearchMatch]
    embedding_tokens: int
    chat_tokens: int
    search_query: str = ""  # 实际拿去检索的完整问题。
    rewrite_tokens: int = 0  # 本次改写消耗的Token。
    quotes: list[EvidenceQuote] = Field(default_factory=list)  # 返回校验后的摘录；澄清和资料不足时为空。
