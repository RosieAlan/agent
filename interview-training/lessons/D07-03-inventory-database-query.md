# D07：建表、写入样例与库存查询。日期：11/02

对应原第五章5.1至5.3数据库关系/约束/持久化/访问层；先用SQLAlchemy Core显式SQL建立理解，ORM模型和Alembic版本迁移在本D后续继续。业务源码由学生实现，当前教师仅维护讲义与证据。

入口GET /inventory/{sku}→main.inventory_detail(sku)→inventory_repository.get_inventory_from_db(user_id,store_id,sku)→复用db.engine→PostgreSQL JOIN查询→字典→JSON。准备阶段：直接运行inventory_repository.py→initialize_inventory_demo()→建表与补样例。导入只加载函数，初始化由直接运行命令触发。db.py及现有广告工具/绑定/循环均沿用。

必备新知识：事务engine.begin正常结束提交/异常回滚；CREATE TABLE/INSERT/SELECT分别建表/写入/读取；JOIN依据店铺编号关联；SQLAlchemy命名参数传值，不拼接用户输入；mappings按列名取值，one_or_none零行返回None/一行返回记录/多行报错；dict|None是两种可能返回值，->None表示函数无有意义返回结果；模块主入口保护初始化副作用。IF NOT EXISTS与ON CONFLICT只服务本课初始结构/样例重复执行，后续结构变化使用版本迁移。

当前HTTP演示身份固定user-001/store-A，接口绑定本机127.0.0.1；登录校验和动态店铺授权待后续接入，此入口不计真实鉴权完成。仓储函数查询同时限定user/store/sku。两店相同SKU分别12与88；样例来源synthetic_demo，真实数据库存储与真实外部数据分开记录。

学生新增inventory_repository.py完整代码：

```python
from sqlalchemy import text  # 沿用SQL文本包装工具。
from db import engine  # 复用db.py中的连接管理对象。


def initialize_inventory_demo() -> None:
    """创建课程表，并补入合成样例记录。"""
    # 事务：全部成功时提交；出现异常时，本次修改全部回滚。
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS stores (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL
            )
        """))  # 店铺表：保存店铺及所属用户。

        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS inventory (
                id TEXT PRIMARY KEY,
                store_id TEXT NOT NULL REFERENCES stores(id),
                sku TEXT NOT NULL,
                stock INTEGER NOT NULL CHECK (stock >= 0),
                threshold INTEGER NOT NULL CHECK (threshold >= 0),
                data_source TEXT NOT NULL,
                UNIQUE (store_id, sku)
            )
        """))  # 库存表：同一个店铺的同一个商品只保存一条记录。

        connection.execute(text("""
            INSERT INTO stores (id, user_id, name)
            VALUES
                ('store-A', 'user-001', 'Demo store A'),
                ('store-B', 'user-002', 'Demo store B')
            ON CONFLICT (id) DO NOTHING
        """))  # 已有相同店铺编号时保留原记录。

        connection.execute(text("""
            INSERT INTO inventory
                (id, store_id, sku, stock, threshold, data_source)
            VALUES
                ('inv-A', 'store-A', 'SKU-DEMO-001', 12, 20, 'synthetic_demo'),
                ('inv-B', 'store-B', 'SKU-DEMO-001', 88, 20, 'synthetic_demo')
            ON CONFLICT (store_id, sku) DO NOTHING
        """))  # 重复初始化时保留已经存在的库存值。


def get_inventory_from_db(
    user_id: str, store_id: str, sku: str
) -> dict | None:  # 找到返回字典，未找到返回None。
    with engine.connect() as connection:
        row = connection.execute(
            text("""
                SELECT i.data_source, i.store_id, i.sku, i.stock, i.threshold
                FROM inventory AS i
                JOIN stores AS s ON s.id = i.store_id
                WHERE s.user_id = :user_id
                  AND i.store_id = :store_id
                  AND i.sku = :sku
            """),  # 通过店铺关联，限定用户、店铺和商品。
            {"user_id": user_id, "store_id": store_id, "sku": sku},
        ).mappings().one_or_none()  # 按列名取结果，预期零条或一条。

    if row is None:
        return None  # 由HTTP层决定返回404。

    result = dict(row)  # 将查询记录转换成普通字典。
    result["is_low_stock"] = result["stock"] < result["threshold"]
    return result  # 返回真实数据库里保存的合成样例记录。


if __name__ == "__main__":  # 直接运行本文件时执行；被import时跳过。
    initialize_inventory_demo()  # 初始化只由明确的命令触发。
    print("课程店铺表、库存表及样例数据已准备好")
```

main新增导入`from inventory_repository import get_inventory_from_db`和`from sqlalchemy.exc import OperationalError`，已有SQLAlchemyError/HTTPException沿用；末尾新增：

```python
@app.get("/inventory/{sku}")  # 当前本地演示入口：按商品编号查询库存。
def inventory_detail(sku: str):
    try:
        result = get_inventory_from_db(
            user_id="user-001",  # 本地演示身份；后续从登录凭据取得。
            store_id="store-A",  # 本地演示店铺；后续校验店铺访问权限。
            sku=sku,  # 使用URL中的商品编号。
        )
    except OperationalError as error:
        raise HTTPException(
            status_code=503, detail="数据库暂时无法访问"
        ) from error  # 数据库连接等运行问题。
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=500, detail="库存查询失败，请检查后端和数据库结构"
        ) from error  # 例如初始化遗漏导致表不存在。

    if result is None:
        raise HTTPException(status_code=404, detail="未找到可访问的商品库存")
    return result  # FastAPI把字典转换为JSON响应。
```

运行（lab目录）：`.\.venv\Scripts\python.exe inventory_repository.py`。直接运行时会初始化；重复运行保留已有记录。保持8000后端运行，浏览器GET http://127.0.0.1:8000/inventory/SKU-DEMO-001 预期source synthetic_demo/store-A/stock12/threshold20/is_low_stock true；未知SKU返回404。独立修改使用课程库UPDATE将store-A库存改25，查询应变false且原Python工具常量保持不变；具体更新接口/工具回接后续实现，当前不虚构学生运行。

教师先确认候选查询尚未实现，再在真实PostgreSQL事务内的独立schema验证：重复初始化仅2条库存；跨用户/店铺查询None；缺SKU/注入文本参数None；两店同SKU独立；12低库存/25正常；非负/外键/唯一约束。事务回滚后检查schema不存在，临时制品已清理。模型供应商调用0次。HTTP候选验证见PROGRESS，学生集成待提交。

必背：参数化SQL分开传指令和数据；用户作用域进入查询条件；数据库约束守住数据规则；事务让一组修改一起提交或回滚。IF NOT EXISTS只保证已有表时跳过创建，已有表的结构升级通过迁移记录管理。

官方依据：https://docs.sqlalchemy.org/en/21/tutorial/dbapi_transactions.html 、https://www.postgresql.org/docs/16/sql-insert.html 。

