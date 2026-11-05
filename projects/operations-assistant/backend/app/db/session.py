from functools import lru_cache

from sqlalchemy import create_engine

from app.core.config import get_settings
from app.db.target import local_project_url


@lru_cache
def get_engine():
    settings = get_settings()
    # 日常查询连接本机MySQL项目库，使用独立只读账号。
    return create_engine(local_project_url(settings.database_url), pool_pre_ping=True, pool_size=5, max_overflow=0, pool_timeout=3, pool_recycle=1800, connect_args={"connect_timeout": 5, "read_timeout": 8, "write_timeout": 8, "charset": "utf8mb4", "init_command": "SET time_zone = '+00:00'"})
