import os
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine, pool
from app.db.target import local_project_url

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def run_migrations():
    # 只有迁移账号能建表；URL来自本机配置，避免提交密码。
    engine = create_engine(local_project_url(os.environ["MIGRATION_DATABASE_URL"]), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


run_migrations()
