from functools import lru_cache

from sqlalchemy import create_engine

from app.core.config import get_settings
from app.db.target import local_project_url


@lru_cache
def get_engine():
    settings = get_settings()
    # 日常查询使用项目自己的PostgreSQL；公司MySQL仅供导入脚本读取。
    return create_engine(local_project_url(settings.database_url), pool_pre_ping=True, pool_size=5, max_overflow=0, pool_timeout=3, pool_recycle=1800, connect_args={"connect_timeout": 5, "options": "-c statement_timeout=8000 -c default_transaction_read_only=on"})
