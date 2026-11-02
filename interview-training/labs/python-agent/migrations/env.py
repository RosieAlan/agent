from logging.config import fileConfig

from alembic import context
from db import database_url, engine  # 复用.env配置，密码留在本机。
from models import Base  # 导入并登记Store、Inventory模型。

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)  # 加载迁移命令的日志配置。

target_metadata = Base.metadata  # 自动比较时使用的目标表结构。


def configure_and_run(connection) -> None:
    context.configure(
        connection=connection,  # 本次迁移实际使用的数据库连接。
        target_metadata=target_metadata,
        compare_type=True,  # 比较模型和数据库的字段类型。
    )
    with context.begin_transaction():  # 支持事务的DDL由事务保护。
        context.run_migrations()  # 按版本关系执行迁移操作。


def run_migrations_online() -> None:
    # 测试或部署脚本可以传入已有连接，以便统一控制事务。
    connection = config.attributes.get("connection")
    if connection is not None:
        configure_and_run(connection)
    else:
        with engine.connect() as connection:  # 普通命令从连接池获取连接。
            configure_and_run(connection)


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,  # 用于生成SQL，连接配置不写入Git配置文件。
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()  # --sql模式只输出SQL，供发布前审查。


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
