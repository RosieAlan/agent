"""Explicit one-off additive schema initialization; credentials remain in environment."""
import asyncio
import os
from pathlib import Path

import pymysql
import psycopg
from psycopg import sql


def main():
    name = os.environ["DB_NAME"]
    conn = pymysql.connect(host="mysql", user="root", password=os.environ["MYSQL_ROOT_PASSWORD"],
                           database=name, charset="utf8mb4", autocommit=True)
    try:
        with conn.cursor() as cur:
            for path in (Path("/business.sql"), Path("scripts/operations_schema.sql")):
                # Project MySQL schema contains ordinary DDL/DML; procedures use a separate migration.
                for statement in path.read_text(encoding="utf-8").split(";"):
                    if statement.strip():
                        cur.execute(statement)
    finally:
        conn.close()
    from scripts.init_checkpoints import main as init_checkpoints
    asyncio.run(init_checkpoints())
    if os.environ.get("KNOWLEDGE_DATABASE_URL"):
        database, role = os.environ["PG_DATABASE"], os.environ["PG_APP_USER"]
        with psycopg.connect(host="postgres", dbname=database, user="postgres",
                              password=os.environ["PG_ADMIN_PASSWORD"], autocommit=True) as pg:
            with pg.cursor() as cur:
                cur.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,))
                if cur.fetchone() is None:
                    cur.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                        sql.Identifier(role), sql.Literal(os.environ["PG_APP_PASSWORD"])))
            with pg.transaction():
                pg.execute(Path("scripts/knowledge_schema.sql").read_text(encoding="utf-8"))
                for path in sorted(Path("scripts/knowledge_migrations").glob("*.sql")):
                    pg.execute(path.read_text(encoding="utf-8"))
                pg.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(database), sql.Identifier(role)))
                pg.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role)))
                pg.execute(sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}").format(sql.Identifier(role)))
    print("Business, automation, checkpoints and enabled knowledge schemas initialized")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Database errors can contain credentials, SQL and private record contents.
        print("Schema initialization failed: " + type(exc).__name__)
        raise SystemExit(1) from None
