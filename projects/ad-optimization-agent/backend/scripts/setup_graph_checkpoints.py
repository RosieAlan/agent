"""在第二项目本机业务库初始化检查点表；运行账号保留数据读写权限。"""

import json
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pymysql
from langgraph.checkpoint.mysql.pymysql import PyMySQLSaver

from app.db.business import business_engine


def main():
    url = business_engine().url
    if url.host != "127.0.0.1" or url.port != 3307 or url.database != "ad_agent_business":
        raise RuntimeError("检查点初始化仅支持本项目本机业务库")
    info = json.loads(subprocess.run(["docker", "inspect", "operations-mysql"],
        capture_output=True, text=True, check=True).stdout)[0]
    variables = dict(item.split("=", 1) for item in info["Config"]["Env"] if "=" in item)
    with pymysql.connect(host="127.0.0.1", port=3307, user="root",
        password=variables["MYSQL_ROOT_PASSWORD"], database="ad_agent_business",
        charset="utf8mb4", autocommit=True, connect_timeout=5) as connection:
        PyMySQLSaver(connection).setup()  # 执行检查点包自身的版本迁移，仅部署时运行。
        tables = {match.group(1) for sql in PyMySQLSaver.MIGRATIONS for match in re.finditer(
            r"CREATE TABLE IF NOT EXISTS\s+([A-Za-z_][A-Za-z0-9_]*)", sql, re.IGNORECASE)}
        if not tables:
            raise RuntimeError("未识别检查点迁移表，请核对依赖版本")
        with connection.cursor() as cursor:
            for table in tables:
                cursor.execute(f"GRANT SELECT,INSERT,UPDATE ON ad_agent_business.`{table}` TO 'ad_agent_app'@'%'")
    print("Graph checkpoint tables ready:", ", ".join(sorted(tables)))


if __name__ == "__main__":
    main()
