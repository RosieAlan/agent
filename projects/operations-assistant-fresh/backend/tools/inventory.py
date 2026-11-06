from langchain_core.tools import tool  # 将函数包装成模型工具。
from pydantic import BaseModel, Field  # 定义工具参数及校验规则。

from services import inspect_inventory  # 调用已有库存检查业务。


class InventoryToolInput(BaseModel):
    """库存检查工具接受的参数。"""

    sku: str = Field(
        min_length=1,
        max_length=64,
        description="商品编号，例如OPS-EARBUDS-001",
    )

    threshold: int = Field(
        default=20,
        ge=0,
        le=1_000_000,
        description="低库存阈值，可售数量低于该值时标记异常",
    )


@tool(args_schema=InventoryToolInput)
def check_inventory(sku: str, threshold: int = 20) -> dict:
    """查询指定商品在各演示店铺的库存，并判断低库存。
    返回可售、预留、在途数量和距离阈值的差额。
    数据来源为模拟数据，本工具执行查询与判断。
    """

    # 执行工具时，才会调用业务函数并查询数据库。
    return inspect_inventory(sku, threshold)