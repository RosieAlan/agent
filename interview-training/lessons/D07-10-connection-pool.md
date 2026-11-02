# D07：数据库连接池

日期：2026-11-02。实际D07，日历目标D12。对应原课5.3.4数据库服务的全局复用与连接生命周期。

## 学习目标

必备：连接池复用数据库连接并限制同时占用数量；with结束后归还连接。
熟练：区分pool_timeout借连接等待与connect_timeout新建连接等待；排查连接长期占用。
熟悉：多进程连接预算、池超时映射503、监测占用及等待。应用当前池超时仍走通用SQLAlchemyError处理，专门503映射待接入。

当前db.py使用pool_size=5、max_overflow=0、pool_timeout=5、pool_pre_ping=True。每个进程的这个engine最多同时借出5个连接，第6次申请最多等待5秒。连接按需创建。用户和HTTP请求可以分时复用这些连接。

## 实验

学生可在labs/python-agent新建pool_demo.py；业务db.py配置沿用。实验使用独立engine，完成后释放全部实验连接。

```python
from sqlalchemy import create_engine, text
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from db import database_url  # 只复用连接配置；实验使用单独的连接池。

test_engine = create_engine(
    database_url,
    pool_size=2,       # 为了观察现象，实验池只允许保留2个连接。
    max_overflow=0,    # 额外连接数为0。
    pool_timeout=1,    # 借不到连接时，最多等待1秒。
    connect_args={"connect_timeout": 5},  # 新建数据库连接最多等待5秒。
)

connections = []  # 保存本次实验借出的连接，最后统一归还。

try:
    for number in range(2):  # 连续借出两个连接，暂时都保留着。
        connections.append(test_engine.connect())
        print("已借出连接数：", test_engine.pool.checkedout())

    try:
        with test_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except PoolTimeoutError:
        print("第三次借连接：等待1秒后超时")  # 两个连接都被占用。

    connections.pop().close()  # 取出其中一个连接并归还连接池。
    print("归还一个后，已借出：", test_engine.pool.checkedout())

    with test_engine.connect() as connection:  # 现在可以再次借到连接。
        result = connection.execute(text("SELECT 1")).scalar_one()
        print("再次借到连接，查询结果：", result)
    # 离开with，这次借到的连接也已经归还。

finally:
    for connection in connections:
        connection.close()  # 发生异常时也归还仍持有的连接。
    print("清理后，已借出：", test_engine.pool.checkedout())
    test_engine.dispose()  # 结束实验，关闭实验池中的空闲连接。

```

在python-agent目录运行：

```powershell
.\.venv\Scripts\python.exe pool_demo.py
```

教师已通过stdin在真实本地PostgreSQL验证，输出：

```text
已借出连接数： 1
已借出连接数： 2
第三次借连接：等待1秒后超时
归还一个后，已借出： 1
再次借到连接，查询结果： 1
清理后，已借出： 0
```

PoolTimeoutError是SQLAlchemy TimeoutError的导入别名；checkedout返回当前借出数量；close归还池连接；dispose关闭已归还的实验池空闲连接。with engine.begin同时负责成功提交、异常回滚和连接归还。

## 生产要求与必背答案

连接池复用连接，降低重复建连开销，并限制数据库并发占用。通过with确保异常时也归还连接。池等待超时后检查连接泄漏、长事务、慢SQL和连接总预算，再决定调整池大小。模型调用和外部HTTP等待应安排在短数据库事务之外。

4个服务进程各配置5个连接，上限合计20，还需计算数据库管理工具、迁移与其他服务。pool_pre_ping检查连接有效性，事务失败重试需单独设计。全局engine与应用关闭清理的设计，对应原课全局PrismaService初始化/销毁；本项目显式应用关闭dispose尚待接入。

参考：https://docs.sqlalchemy.org/en/21/core/pooling.html

## 证据与剩余

教师实验已通过，业务库存未写入，模型调用0次。学生实验输出待收，可与D07综合检查合并。前一块学生EXPLAIN实际0.048ms、两处索引扫描、结果1行，执行计划读取块通过。D07其余既定模型、事务与综合验收继续，完整独立通过仍1/32。

