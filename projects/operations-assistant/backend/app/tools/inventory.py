from typing import Annotated  # 给参数附加校验说明。

from langchain_core.tools import tool  # 将Python函数封装成模型工具。
from pydantic import Field  # 设置参数长度和描述。

from app.repositories.demo_inventory import find_inventory  # 调用三表查询。


@tool
def get_demo_inventory(
    sku: Annotated[
        str,
        Field(
            min_length=1,
            max_length=64,
            description="商品编号，例如OPS-EARBUDS-001",
        ),
    ],
) -> dict:
    """根据商品编号查询各店铺模拟库存，返回店铺、商品、可售、预留和在途数量。"""

    # 后端执行到这里时，才实际调用数据库查询函数。
    inventories = find_inventory(sku.strip())

    return {
        "data_source": "synthetic_demo",  # 明确标记模拟数据。
        "found": bool(inventories),       # 查到记录为True，空列表为False。
        "sku": sku,                       # 本次查询的商品编号。
        "inventories": inventories,       # 各店铺的库存列表。
    }