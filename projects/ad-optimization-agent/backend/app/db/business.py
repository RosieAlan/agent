"""第二项目自有MySQL连接池，保存草案和审批记录。"""

from functools import lru_cache
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL


@lru_cache(maxsize=1)
def business_engine():
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    if any(not os.getenv(f"APP_DB_{key}") for key in ("HOST", "PORT", "NAME", "USER", "PASSWORD")):
        raise RuntimeError("项目业务数据库尚未配置")
    return create_engine(URL.create(
        "mysql+pymysql", username=os.environ["APP_DB_USER"], password=os.environ["APP_DB_PASSWORD"],
        host=os.environ["APP_DB_HOST"], port=int(os.environ["APP_DB_PORT"]),
        database=os.environ["APP_DB_NAME"], query={"charset": "utf8mb4"},
    ), pool_pre_ping=True, pool_size=3, max_overflow=0, pool_timeout=3, pool_recycle=1200,
        connect_args={"connect_timeout": 4, "read_timeout": 8, "write_timeout": 8})


def business_health():
    with business_engine().connect() as connection:
        database = connection.execute(text("SELECT DATABASE()")).scalar_one()
        return {"status": "ok", "database": database}
