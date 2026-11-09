from sqlalchemy import text  # 将SQL字符串转换成SQLAlchemy可执行语句。
from sqlalchemy.exc import SQLAlchemyError  # 数据库操作异常。

from app.core.errors import DependencyUnavailable  # 项目已有的服务不可用异常。
from app.db.session import get_engine  # 获取项目已有的数据库引擎。


def find_inventory(sku: str) -> list[dict]:
    """按商品编号查询各店铺库存，返回字典列表。"""

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
    """)  # :sku是参数位置，实际值通过execute传入。

    try:
        with get_engine().connect() as connection:
            # 使用参数绑定，将商品编号作为查询条件。
            result = connection.execute(statement, {"sku": sku})

            # 每行按字段名称读取，再取出全部行。
            rows = result.mappings().all()

            # 将数据库行转换成普通Python字典。
            return [dict(row) for row in rows]

        # 离开with代码块时，连接自动归还连接池。

    except SQLAlchemyError as error:
        # 交给项目已有异常处理器，返回HTTP 503。
        raise DependencyUnavailable("库存数据库暂时不可用") from error