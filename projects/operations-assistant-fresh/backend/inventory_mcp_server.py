"""库存 MCP 服务入口：由本机客户端通过 stdio 启动。"""

import logging
from typing import Annotated

from mcp.server import MCPServer  # 官方 SDK：注册工具并处理 MCP 协议。
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field, StringConstraints
from sqlalchemy.exc import SQLAlchemyError

from core.cache import close_cache
from db import engine
from schemas.inventory import InventoryCheckResponse  # 沿用已有库存返回格式。
from services.inventory import inspect_inventory  # 沿用库存检查业务。

logger = logging.getLogger(__name__)
mcp = MCPServer("operations-inventory")  # 客户端看到的服务名称。


@mcp.tool(structured_output=True)  # 注册工具，并将字典作为结构化结果返回。
def check_inventory(
    sku: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)],
    threshold: Annotated[int, Field(ge=0, le=1_000_000)] = 20,
) -> InventoryCheckResponse:
    """查询商品在各演示店铺的库存，按阈值判断低库存。

    数据为synthetic_demo合成样例。返回可售、预留、在途数量和阈值差额。
    该工具仅执行查询；商品编号缺失时，应先向用户询问SKU。
    """
    try:
        result = inspect_inventory(sku, threshold)  # 执行到这里才查询业务数据。
        return InventoryCheckResponse.model_validate(result)  # 校验结果并提供输出Schema。
    except SQLAlchemyError:
        logger.warning("inventory_storage_unavailable")  # 日志走stderr，保留stdout给协议。
        raise ToolError("inventory_storage_unavailable") from None  # 返回固定错误码。


if __name__ == "__main__":  # 直接运行文件时启动；import时只加载定义。
    try:
        mcp.run(transport="stdio")  # 等待客户端通过标准输入发送MCP请求。
    finally:
        close_cache()  # 客户端结束连接后释放本进程的Redis连接池。
        engine.dispose()  # 释放本进程的数据库连接池。
