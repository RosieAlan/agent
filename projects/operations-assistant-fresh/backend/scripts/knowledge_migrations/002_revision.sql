ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS revision INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0);
CREATE UNIQUE INDEX IF NOT EXISTS knowledge_document_identity
ON knowledge_documents (content_hash, parser_version, embedding_model, dimensions);
