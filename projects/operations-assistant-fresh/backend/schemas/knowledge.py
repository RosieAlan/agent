from pydantic import BaseModel  # 约定上传接口返回给浏览器的字段。


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
