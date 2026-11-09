-- 开发环境的第1版知识库迁移。由初始化脚本以管理员身份运行一次。
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS knowledge_documents (
    id CHAR(64) PRIMARY KEY,
    content_hash CHAR(64) NOT NULL,
    filename VARCHAR(255) NOT NULL,
    original_content BYTEA NOT NULL,
    parser_version TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    dimensions INTEGER NOT NULL CHECK (dimensions = 1024),
    chunk_count INTEGER NOT NULL CHECK (chunk_count BETWEEN 1 AND 100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    document_id CHAR(64) NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL CHECK (ordinal > 0),
    content TEXT NOT NULL,
    metadata JSONB NOT NULL,
    embedding VECTOR(1024) NOT NULL,
    PRIMARY KEY (document_id, ordinal)
);
-- 当前小规模教学库使用精确检索；HNSW/IVF在索引专项中测量后添加。
