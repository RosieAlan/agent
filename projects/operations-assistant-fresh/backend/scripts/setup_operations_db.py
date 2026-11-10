"""通过本机 Docker 管理员创建表；应用账号仅获得所需表的数据权限。"""
import json
import os
import re
import subprocess
from pathlib import Path

from dotenv import load_dotenv


def main():
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / '.env')
    database, user = os.environ['DB_NAME'], os.environ['DB_USER']
    if not all(re.fullmatch(r'[A-Za-z0-9_]+', value) for value in (database, user)):
        raise RuntimeError('invalid_database_identifier')
    container = 'operations-mysql'
    inspect = subprocess.run(['docker', 'inspect', container], capture_output=True, check=True, text=True)
    env = dict(value.split('=', 1) for value in json.loads(inspect.stdout)[0]['Config']['Env'] if '=' in value)
    admin_password = env.get('MYSQL_ROOT_PASSWORD')
    if not admin_password:
        raise RuntimeError('mysql_admin_configuration_missing')
    schema = (root / 'scripts' / 'operations_schema.sql').read_text(encoding='utf-8')
    tables = re.findall(r'CREATE TABLE IF NOT EXISTS (\w+)', schema)
    grants = '\n'.join(f'GRANT SELECT,INSERT,UPDATE,DELETE ON `{database}`.`{table}` TO \'{user}\'@\'%\';' for table in tables)
    # 密码经进程环境传递到容器命令，不打印 inspect 或子进程错误正文。
    process_env = {**os.environ, 'MYSQL_PWD': admin_password}
    result = subprocess.run(['docker', 'exec', '-i', '-e', 'MYSQL_PWD', container,
                             'mysql', '-uroot', '--default-character-set=utf8mb4', database],
                            input=schema+'\n'+grants, text=True, capture_output=True, env=process_env)
    if result.returncode:
        raise RuntimeError('operations_schema_setup_failed')
    print('operations schema and least-privilege grants ready')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('operations_schema_setup_failed') from None
