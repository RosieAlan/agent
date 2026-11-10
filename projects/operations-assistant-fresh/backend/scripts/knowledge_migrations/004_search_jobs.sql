-- 同步任务随文档修改一起提交，ES暂时不可用时保留待处理记录。
CREATE TABLE IF NOT EXISTS knowledge_search_jobs (
    document_id CHAR(64) PRIMARY KEY,
    revision INTEGER NOT NULL,
    deleted BOOLEAN NOT NULL DEFAULT false,
    queued_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE OR REPLACE FUNCTION enqueue_knowledge_search() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        INSERT INTO knowledge_search_jobs(document_id, revision, deleted)
        VALUES (OLD.id, OLD.revision, true)
        ON CONFLICT(document_id) DO UPDATE SET revision=EXCLUDED.revision, deleted=true, queued_at=now();
        RETURN OLD;
    END IF;
    INSERT INTO knowledge_search_jobs(document_id, revision, deleted)
    VALUES (NEW.id, NEW.revision, false)
    ON CONFLICT(document_id) DO UPDATE SET revision=EXCLUDED.revision, deleted=false, queued_at=now();
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS knowledge_search_changed ON knowledge_documents;
CREATE TRIGGER knowledge_search_changed AFTER INSERT OR UPDATE OR DELETE ON knowledge_documents
FOR EACH ROW EXECUTE FUNCTION enqueue_knowledge_search();
-- 首次安装时，为现有SOP补建搜索索引；重复初始化允许安全重建。
INSERT INTO knowledge_search_jobs(document_id, revision)
SELECT id, revision FROM knowledge_documents ON CONFLICT(document_id) DO NOTHING;
