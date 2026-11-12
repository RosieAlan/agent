"""仅初始化本机operations-mysql中的第二项目独立库，源广告库保持原样。"""

import json
import os
from pathlib import Path
import secrets
import subprocess

from dotenv import dotenv_values, set_key
from pymysql.converters import escape_string


def main():
    root = Path(__file__).resolve().parents[1]
    values = dotenv_values(root / ".env")
    password = values.get("APP_DB_PASSWORD") or secrets.token_urlsafe(24)
    info = json.loads(subprocess.run(["docker", "inspect", "operations-mysql"],
        check=True, capture_output=True, text=True).stdout)[0]
    variables = dict(item.split("=", 1) for item in info["Config"]["Env"] if "=" in item)
    admin = variables["MYSQL_ROOT_PASSWORD"]
    bindings = info["NetworkSettings"]["Ports"].get("3306/tcp") or []
    if not any(item["HostIp"] == "127.0.0.1" and item["HostPort"] == "3307" for item in bindings):
        raise RuntimeError("请核对本机MySQL的127.0.0.1:3307绑定")
    schema = (root / "migrations" / "V001__budget_proposals.sql").read_text(encoding="utf-8")
    # 先保存本机生成的密码，DDL中途失败后可以沿用同一配置继续初始化。
    for key, value in {"HOST": "127.0.0.1", "PORT": "3307", "NAME": "ad_agent_business",
                       "USER": "ad_agent_app", "PASSWORD": password}.items():
        set_key(root / ".env", f"APP_DB_{key}", value)
    sql = f"""
CREATE DATABASE IF NOT EXISTS ad_agent_business CHARACTER SET utf8mb4;
CREATE USER IF NOT EXISTS 'ad_agent_app'@'%' IDENTIFIED BY '{escape_string(password)}';
USE ad_agent_business;
{schema}
GRANT SELECT,INSERT,UPDATE ON ad_agent_business.ad_budget_proposals TO 'ad_agent_app'@'%';
GRANT SELECT,INSERT ON ad_agent_business.ad_proposal_events TO 'ad_agent_app'@'%';
"""
    result = subprocess.run(["docker", "exec", "-i", "-e", "MYSQL_PWD", "operations-mysql",
        "mysql", "-uroot", "--default-character-set=utf8mb4"], input=sql, text=True,
        encoding="utf-8", capture_output=True, env={**os.environ, "MYSQL_PWD": admin})
    if result.returncode:
        raise RuntimeError("独立业务库初始化失败，请检查本机Docker状态")
    print("Business database ready: 127.0.0.1:3307/ad_agent_business")


if __name__ == "__main__":
    main()
