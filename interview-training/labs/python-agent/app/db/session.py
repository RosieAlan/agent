import os  # 读取环境变量。
from pathlib import Path  # 定位项目根目录的.env。

from dotenv import load_dotenv  # 将.env配置加载到环境变量。
from sqlalchemy import URL, create_engine, text  # 数据库连接和SQL执行工具。


# 导入时读取python-agent根目录的.env文件。
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


# 将分开的配置组成数据库连接地址。
database_url = URL.create(
    "postgresql+psycopg",  # 数据库是PostgreSQL，通信驱动是psycopg。
    username=os.environ["PG_USER"],  # 数据库用户名。
    password=os.environ["PG_PASSWORD"],  # 数据库密码。
    host=os.environ["PG_HOST"],  # 数据库地址，当前为127.0.0.1。
    port=int(os.environ["PG_PORT"]),  # 将配置中的字符串端口转为整数。
    database=os.environ["PG_DATABASE"],  # 当前连接agent_training数据库。
)


# 导入db.py时创建；同一个后端进程中的请求共用这个连接管理对象。
engine = create_engine(
    database_url,  # 使用上面准备好的连接配置。
    pool_pre_ping=True,  # 复用旧连接前，检查连接是否仍然有效。
    pool_size=5,  # 连接池最多保留5个连接，按需要创建。
    max_overflow=0,  # 额外新增连接数为0。
    pool_timeout=5,  # 连接全部被占用时，最多等待5秒。
    connect_args={"connect_timeout": 5},  # 建立数据库连接最多等待5秒。
)


def check_database() -> dict:
    """查询当前数据库名称，返回检查结果字典。"""

    # 从engine获取连接；执行完或出现异常时，with负责归还连接。
    with engine.connect() as connection:
        database_name = connection.execute(
            text("SELECT current_database()")  # SQL：查询当前数据库名称。
        ).scalar_one()  # 从查询结果中取出唯一一行的第一列。

    # 返回Python字典，后续由FastAPI转换成JSON响应。
    return {
        "status": "ok",
        "database": database_name,
    }
