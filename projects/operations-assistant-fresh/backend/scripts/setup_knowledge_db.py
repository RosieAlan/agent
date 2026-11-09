"""本机开发初始化：复用Docker中的pgvector，新建独立库和应用账号。"""
import json
from pathlib import Path
import secrets
import subprocess
from dotenv import dotenv_values, set_key
from sqlalchemy.engine import URL, make_url

ROOT = Path(__file__).resolve().parents[1]
DATABASE = "ops_assistant_knowledge"
ROLE = "ops_knowledge_app"


def setup():
    env = dotenv_values(ROOT / ".env")
    existing = env.get("KNOWLEDGE_DATABASE_URL")
    password = make_url(existing).password if existing else secrets.token_urlsafe(28)
    # 捕获容器环境以获取管理员用户名，凭据不输出到终端。
    info = json.loads(subprocess.check_output(["docker", "inspect", "llm-postgres"], text=True))[0]
    container_env = dict(item.split("=", 1) for item in info["Config"]["Env"] if "=" in item)
    admin = container_env.get("POSTGRES_USER", "postgres")

    def sql(statement, database="postgres"):
        result = subprocess.run(
            ["docker", "exec", "-i", "llm-postgres", "psql", "-X", "-v", "ON_ERROR_STOP=1",
             "-U", admin, "-d", database, "-At"],
            input=statement, text=True, encoding="utf-8", capture_output=True,
        )
        if result.returncode:
            raise RuntimeError("知识库初始化失败，请检查Docker和PostgreSQL状态")
        return result.stdout.strip()

    role_exists = sql(f"SELECT 1 FROM pg_roles WHERE rolname='{ROLE}';") == "1"
    if role_exists and not existing:
        raise RuntimeError("同名账号已存在，请恢复原本机知识库配置后重试")
    # 在创建账号前保存本次配置，中途失败也能凭相同账号密码重试。
    url = URL.create("postgresql+psycopg", username=ROLE, password=password,
                     host="127.0.0.1", port=5432, database=DATABASE)
    set_key(ROOT / ".env", "KNOWLEDGE_DATABASE_URL", url.render_as_string(hide_password=False))
    if not role_exists:
        quoted_password = password.replace("'", "''")
        sql(f"CREATE ROLE {ROLE} LOGIN PASSWORD '{quoted_password}';")
    if sql(f"SELECT 1 FROM pg_database WHERE datname='{DATABASE}';") != "1":
        sql(f"CREATE DATABASE {DATABASE};")
    # 建表与授权作为一个事务提交，失败时整体回滚。
    schema = (ROOT / "scripts" / "knowledge_schema.sql").read_text(encoding="utf-8")
    for migration in sorted((ROOT / "scripts" / "knowledge_migrations").glob("*.sql")):
        schema += "\n" + migration.read_text(encoding="utf-8")
    sql(f"BEGIN;\n{schema}\nGRANT CONNECT ON DATABASE {DATABASE} TO {ROLE};\n"
        f"GRANT USAGE ON SCHEMA public TO {ROLE};\n"
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON knowledge_documents, knowledge_chunks TO {ROLE};\nCOMMIT;", DATABASE)
    print(f"Knowledge database ready: {DATABASE}; connection saved to local .env")


if __name__ == "__main__":
    setup()
