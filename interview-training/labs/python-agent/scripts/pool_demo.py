from sqlalchemy import create_engine, text
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from app.db.session import database_url  # 复用数据库配置。

test_engine = create_engine(
    database_url,
    pool_size=2,       # 实验池最多保留2个连接。
    max_overflow=0,    # 额外连接数为0。
    pool_timeout=1,    # 借不到连接时，最多等待1秒。
    connect_args={"connect_timeout": 5},  # 新建连接最多等待5秒。
)

connections = []  # 保存实验中借出的连接，方便最后清理。

try:
    for number in range(2):
        connections.append(test_engine.connect())  # 借连接，暂时保留。
        print("已借出连接数：", test_engine.pool.checkedout())

    try:
        with test_engine.connect() as connection:  # 尝试借第3个连接。
            connection.execute(text("SELECT 1"))
    except PoolTimeoutError:
        print("第三次借连接：等待1秒后超时")

    connections.pop().close()  # 从列表取出一个连接，并归还连接池。
    print("归还一个后，已借出：", test_engine.pool.checkedout())

    with test_engine.connect() as connection:  # 再次申请，现在可以借到。
        result = connection.execute(text("SELECT 1")).scalar_one()
        print("再次借到连接，查询结果：", result)

finally:
    for connection in connections:
        connection.close()  # 归还实验中仍然持有的连接。

    print("清理后，已借出：", test_engine.pool.checkedout())
    test_engine.dispose()  # 关闭实验池中的空闲连接。
