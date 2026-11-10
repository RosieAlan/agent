from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import URL

from app.core.config import source_settings

settings = source_settings()
source_engine = create_engine(
    URL.create(
        "mysql+pymysql", username=settings.user, password=settings.password,
        host=settings.host, port=settings.port, database=settings.database,
        query={"charset": "utf8mb4"},
    ),
    pool_pre_ping=True,
    pool_size=3, max_overflow=0, pool_timeout=3, pool_recycle=1200,
    connect_args={"connect_timeout": 4, "read_timeout": 8, "write_timeout": 4},
)  # 创建连接池；实际数据库连接在执行查询时建立。


@event.listens_for(source_engine, "connect")
def configure_read_only(dbapi_connection, connection_record):
    # 每个新连接都设为只读；这些SET仅改变本连接的会话设置。
    with dbapi_connection.cursor() as cursor:
        cursor.execute("SET SESSION TRANSACTION READ ONLY")
        cursor.execute("SET SESSION MAX_EXECUTION_TIME=5000")  # 查询执行时间上限5秒。


def source_health() -> dict:
    with source_engine.connect() as connection:
        row = connection.execute(text(
            "SELECT 1 AS result, @@session.tx_read_only AS read_only"
        )).mappings().one()
        return {"status": "ok", "result": row["result"], "read_only": bool(row["read_only"])}
    # 退出连接上下文时回滚读取事务，并将连接归还池中。
