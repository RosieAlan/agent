-- 同一个向量模型下，文件名唯一，支持直接上传新版。
CREATE UNIQUE INDEX IF NOT EXISTS knowledge_document_filename
ON knowledge_documents (embedding_model, filename);
