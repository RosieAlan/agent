from typing import Annotated

from langchain_core.tools import tool
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.errors import DependencyUnavailable
from app.db.session import get_engine


@tool
def get_demo_inventory(msku: Annotated[str, Field(min_length=1, max_length=128)]) -> dict:
    """查询演示店铺的模拟库存。msku为商品编号，返回可售、预留和在途数量。"""
    try:
        with get_engine().connect() as connection:
            connection.exec_driver_sql("START TRANSACTION READ ONLY")
            # 参数绑定；该工具仅查询专门的合成数据表。
            row = connection.execute(text("""
                SELECT store_id, account, msku, sku, product_name,
                       available, reserved, inbound, imported_at
                FROM demo_inventory
                WHERE store_id = :store_id AND msku = :msku
            """), {"store_id": "DEMO-STORE-001", "msku": msku.strip()}).mappings().first()
        if row is None:
            return {"data_source": "synthetic_demo", "found": False, "msku": msku}
        result = dict(row)
        result["imported_at"] = result["imported_at"].isoformat() + "Z"  # 合成数据生成时间，UTC。
        return {"data_source": "synthetic_demo", "found": True, "inventory": result}
    except SQLAlchemyError as error:
        raise DependencyUnavailable("模拟库存数据库暂时不可用") from error
