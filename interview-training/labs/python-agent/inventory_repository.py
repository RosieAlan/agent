from sqlalchemy import select  # 构造查询语句。
from sqlalchemy.orm import Session  # 管理本次数据库操作。
from models import Store, Inventory  # 导入刚定义的两张表模型。
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
    user_id: str,
    store_id: str,
    sku: str,
) -> dict | None:
    """读取指定用户所属店铺的一条库存记录。"""

    with Session(engine) as session:
        # 创建本次查询使用的Session。
        # engine继续复用db.py中的连接池。
        # 离开with时关闭Session，并归还连接。

        statement = (
            select(Inventory)
            # 准备读取库存记录。
            # 此时只是在组装查询，尚未访问数据库。
            .join(
                Store,
                Store.id == Inventory.store_id,
            )
            # 通过店铺编号，关联店铺表和库存表。
            .where(
                Store.user_id == user_id,
                # 检查店铺是否属于当前用户。
                Inventory.store_id == store_id,
                # 限定本次查询的店铺。
                Inventory.sku == sku,
                # 限定本次查询的商品。
            )
        )

        item = session.scalars(statement).one_or_none()
        # scalars(statement)：真正执行查询，取得库存对象。
        # one_or_none()：找到一条就返回对象，没找到返回None。
        # 查出多条时抛出异常，暴露数据或查询条件问题。

        if item is None:
            return None
            # main.py收到None后，沿用原有逻辑返回404。

        return {
            "data_source": item.data_source,
            "store_id": item.store_id,
            "sku": item.sku,
            "stock": item.stock,
            "threshold": item.threshold,
            "is_low_stock": item.stock < item.threshold,
        }
        # 在Session关闭前读取属性并组装字典。
        # 字典交给main.py，再由FastAPI转换成JSON。


def update_inventory_in_db(
    user_id: str, store_id: str, sku: str, stock: int
) -> dict | None:
    """修改当前用户所属店铺的商品库存，返回修改后的记录。"""
    with engine.begin() as connection:  # 成功提交，异常回滚，结束时归还连接。
        row = connection.execute(
            text("""
                UPDATE inventory AS i
                SET stock = :stock
                FROM stores AS s
                WHERE s.id = i.store_id
                  AND s.user_id = :user_id
                  AND i.store_id = :store_id
                  AND i.sku = :sku
                RETURNING i.data_source, i.store_id, i.sku, i.stock, i.threshold
            """),  # 同时限定用户、店铺和商品，再返回更新结果。
            {
                "user_id": user_id,
                "store_id": store_id,
                "sku": sku,
                "stock": stock,
            },  # 参数单独绑定，继续沿用原来的更新方式。
        ).mappings().one_or_none()

    if row is None:
        return None  # main.py收到None后返回404。
    result = dict(row)  # 事务提交后，将记录转换为普通字典。
    result["is_low_stock"] = result["stock"] < result["threshold"]
    return result


if __name__ == "__main__":  # 直接运行本文件时执行；被import时跳过。
    initialize_inventory_demo()  # 初始化由明确的命令触发。
    print("课程店铺表、库存表及样例数据已准备好")
