from typing import Literal

from pydantic import BaseModel, Field


class InventoryItem(BaseModel):
    """一条店铺库存记录。"""

    store_code: str
    store_name: str
    sku: str
    product_name: str
    available: int = Field(ge=0)  # 可售库存必须大于等于0。
    reserved: int = Field(ge=0)   # 预留库存必须大于等于0。
    inbound: int = Field(ge=0)    # 在途库存必须大于等于0。


class InventoryResponse(BaseModel):
    """整个库存查询接口的返回格式。"""

    data_source: Literal["synthetic_demo"]  # 当前数据源固定为模拟数据。
    sku: str
    items: list[InventoryItem]  # 可以包含多家店铺的库存。

class InventoryCheckItem(InventoryItem):
    """沿用已有库存字段，再增加检查结果。"""

    is_low_stock: bool  # 是否低库存。
    gap_to_threshold: int = Field(ge=0)  # 距离本次阈值的差额。


class InventoryCheckResponse(BaseModel):
    data_source: Literal["synthetic_demo"]
    sku: str
    threshold: int = Field(ge=0)
    low_stock_count: int = Field(ge=0)
    items: list[InventoryCheckItem]