import os  # 读取环境变量。
from pathlib import Path  # 定位当前文件所在目录。

from dotenv import load_dotenv  # 加载本地.env配置。
from sqlalchemy import create_engine  # 创建数据库引擎。
from sqlalchemy.engine import URL  # 安全组装连接地址。

# 明确读取db.py旁边的.env；系统已有的环境变量优先生效。
load_dotenv(Path(__file__).resolve().parent / ".env")

database_url = URL.create(
    drivername="mysql+pymysql",       # 使用PyMySQL连接MySQL。
    username=os.environ["DB_USER"],   # 缺少必需配置时，启动直接报错。
    password=os.environ["DB_PASSWORD"],
    host=os.environ["DB_HOST"],
    port=int(os.environ["DB_PORT"]),  # 环境变量是字符串，转换成整数。
    database=os.environ["DB_NAME"],
    query={"charset": "utf8mb4"},     # 支持中文等字符。
)

# 每个后端进程创建一个引擎，后续请求共用它的连接池。
engine = create_engine(
    database_url,
    pool_pre_ping=True,  # 借出连接前检查是否仍然有效。
    pool_size=5,        # 当前进程最多保留5个池内连接。
    max_overflow=0,     # 当前配置最多同时借出5个连接。
    pool_timeout=3,     # 等待空闲连接超过3秒就报错。
    pool_recycle=1800,  # 借出时更新超过1800秒的旧连接。
    connect_args={
        "connect_timeout": 5,  # 建立数据库连接的等待上限。
        "read_timeout": 8,     # 等待数据库返回数据的上限。
        "write_timeout": 8,    # 向数据库发送数据的等待上限。
    },
)