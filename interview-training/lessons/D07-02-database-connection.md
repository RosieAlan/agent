# D07：db.py连接PostgreSQL。日期：10/29

对应原课5.1至5.3的数据库访问基础；Python主线采用当前SQLAlchemy 2.1.6及psycopg 3.3.6，原Prisma设计及后续迁移继续。重点必备：配置加载/连接复用/执行SQL/连接归还；熟练：数据库失败映射503。目标入口GET /health/db，仅检查连接与当前数据库。

调用链：浏览器GET /health/db → main.database_health() → db.check_database() → engine.connect() → PostgreSQL执行SELECT current_database() → 返回字典 → FastAPI转换JSON。错误：驱动错误经SQLAlchemyError传到main，main映射HTTP 503及通用提示。模型调用服务本轮沿用，此健康检查不触发模型请求。

教师已安装SQLAlchemy==2.1.6和psycopg[binary]==3.3.6，在Git忽略的lab/.env补齐PG_HOST/PG_PORT/PG_DATABASE/PG_USER/PG_PASSWORD，复用既有容器密码且未输出。学生在lab新增db.py，main顶部增加导入并在末尾增加GET路由；业务代码供学生在对话按注释实现。

配置含义：PG_HOST=127.0.0.1；PG_PORT=5432；PG_DATABASE=agent_training；PG_USER=llm；PG_PASSWORD保持本机值。系统环境变量优先于load_dotenv默认加载，修改配置后重启后端。

```python
import os  # 读取进程中的环境变量。
from pathlib import Path  # 定位当前文件旁边的.env。
from dotenv import load_dotenv  # 将.env内容加载到环境变量。
from sqlalchemy import URL, create_engine, text  # 连接配置、连接管理、SQL对象。

load_dotenv(Path(__file__).with_name('.env'))  # 模块加载时读取本文件旁边的.env。

database_url = URL.create(
    'postgresql+psycopg',  # PostgreSQL数据库，使用psycopg驱动。
    username=os.environ['PG_USER'],  # 数据库用户；缺配置会在启动时明确报错。
    password=os.environ['PG_PASSWORD'],  # 本机数据库密码。
    host=os.environ['PG_HOST'],  # 本机地址。
    port=int(os.environ['PG_PORT']),  # 将字符串端口转为整数。
    database=os.environ['PG_DATABASE'],  # 目标课程库。
)

engine = create_engine(
    database_url,  # 传入连接配置；创建engine时尚未建立实际数据库连接。
    pool_pre_ping=True,  # 使用池中旧连接前检查有效性。
    pool_size=5,  # 单进程连接池最多保留5个连接，按需建立。
    max_overflow=0,  # 连接池满时，额外新增连接数为0。
    pool_timeout=5,  # 等待池中空闲连接最多5秒。
    connect_args={'connect_timeout': 5},  # 驱动建立数据库连接的超时为5秒。
)

def check_database() -> dict:  # 返回数据库检查结果字典。
    with engine.connect() as connection:  # 获取连接；退出with时归还连接池。
        database_name = connection.execute(
            text('SELECT current_database()')  # 执行只读SQL，获取当前数据库名。
        ).scalar_one()  # 提取唯一一行中的第一列；本查询返回一个数据库名。
    return {'status': 'ok', 'database': database_name}  # 字典交给HTTP层。
```

main顶部增加`from db import check_database`和`from sqlalchemy.exc import SQLAlchemyError`；main末尾新增：

```python
@app.get('/health/db')  # 浏览器GET请求进入此函数。
def database_health():  # 同步数据库调用；FastAPI将此同步路由放在线程池中执行。
    try:
        return check_database()  # main.py调用db.py，返回检查结果。
    except SQLAlchemyError as error:  # 捕获数据库访问与连接池相关错误。
        raise HTTPException(
            status_code=503,  # 依赖的数据库暂时不可用。
            detail='数据库暂时无法连接，请检查数据库服务和连接配置',  # 通用提示。
        ) from error  # 异常链保留给服务端排查。
```

新API：URL.create将分开的连接字段组成配置，自动处理密码特殊字符；engine为模块级连接管理对象，每个进程复用；with负责异常/正常路径的连接释放；text把SQL文本变成可执行对象；execute执行并返回结果；scalar_one提取单个结果。同步def路由由FastAPI在线程池执行，本例使用同步驱动，不加await。

验收：启动8000后端，访问http://127.0.0.1:8000/health/db，预期200与{"status":"ok","database":"agent_training"}；/docs中可见GET /health/db。教师在独立内存测试应用上用真实PostgreSQL验证200/库名/归还连接，并用错误端口验证503与响应不泄露密码。未创建业务db.py/main路由，学生集成证据待提交。测试数据与测试程序均在内存，供应商调用0次。

必背：db.py集中管理数据库连接；engine按进程复用，实际连接在connect时取得；with保证连接使用后归还；main负责把服务结果变HTTP响应，并把数据库不可用映射503。数据库暂时不可用与HTTP输入校验失败分别在访问数据库阶段与入参阶段处理。

官方依据：https://docs.sqlalchemy.org/en/21/core/engines.html 、https://www.psycopg.org/psycopg3/docs/basic/install.html 、https://fastapi.tiangolo.com/async/ 。
