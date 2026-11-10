-- 父块只保存原文；子块继续存入knowledge_chunks并参与检索。
CREATE TABLE IF NOT EXISTS knowledge_parents (
    document_id CHAR(64) NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    parent_id TEXT NOT NULL,
    content TEXT NOT NULL CHECK (char_length(content) BETWEEN 1 AND 2400),
    PRIMARY KEY (document_id, parent_id)
);
