"""SOP知识库专用连接池；业务MySQL继续由db.py管理。"""
import os
from threading import Lock
from sqlalchemy import create_engine

_engine = None
_engine_lock = Lock()


def knowledge_engine():
    global _engine
    with _engine_lock:  # 防止首次并发请求各自创建连接池。
        if _engine is None:
            url = os.getenv("KNOWLEDGE_DATABASE_URL")
            if not url:
                raise RuntimeError("请先初始化知识库数据库")
            # 按需创建一次连接池；配置与凭据只从本机环境读取。
            _engine = create_engine(
                url, pool_size=3, max_overflow=0, pool_timeout=3,
                pool_pre_ping=True, hide_parameters=True,
                connect_args={"connect_timeout": 5, "options": "-c statement_timeout=8000"},
            )
    return _engine


def close_knowledge_engine():
    if _engine is not None:
        _engine.dispose()
