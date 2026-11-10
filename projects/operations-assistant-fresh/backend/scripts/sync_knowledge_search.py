"""手动重试搜索同步：在backend目录执行 python -m scripts.sync_knowledge_search。"""
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import text

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from core.knowledge_db import knowledge_engine, close_knowledge_engine
from services.knowledge_keyword import sync_pending


if __name__ == "__main__":
    try:
        done = sync_pending()
        with knowledge_engine().connect() as conn:
            pending = conn.execute(text("SELECT count(*) FROM knowledge_search_jobs")).scalar()
        print(f"Search sync completed: {done}; pending: {pending}")
    finally:
        close_knowledge_engine()
