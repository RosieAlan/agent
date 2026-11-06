from sqlalchemy import text

from db import engine  # 使用当前项目自己的数据库连接池。


def find_inventory(sku: str) -> list[dict]:
    """根据商品编号，查询各店铺库存。"""

    statement = text("""
        SELECT
            s.code AS store_code,
            s.name AS store_name,
            p.sku,
            p.name AS product_name,
            i.available,
            i.reserved,
            i.inbound
        FROM ops_inventory AS i
        JOIN ops_products AS p ON i.product_id = p.id
        JOIN ops_stores AS s ON i.store_id = s.id
        WHERE p.sku = :sku
        ORDER BY s.code
    """)

    with engine.connect() as connection:  # 获取连接，用完自动归还。
        rows = connection.execute(
            statement,
            {"sku": sku},  # 将参数传给SQL中的:sku。
        ).mappings().all()  # 按字段名称读取全部结果。

        return [dict(row) for row in rows]  # 转成普通字典列表。