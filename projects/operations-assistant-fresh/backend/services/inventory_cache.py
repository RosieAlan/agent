import json
import logging

from pydantic import TypeAdapter, ValidationError
from redis.exceptions import RedisError

from core.cache import redis_client
from repositories.inventory import find_inventory
from schemas.inventory import InventoryItem

logger = logging.getLogger("uvicorn.error")
inventory_rows = TypeAdapter(list[InventoryItem])  # 复用库存结构，检查缓存中的记录。
CACHE_TTL_SECONDS = 10


def find_inventory_cached(sku: str) -> list[dict]:
    """缓存原始库存记录；低库存阈值判断继续由业务函数执行。"""
    if redis_client is None:
        return find_inventory(sku)  # 部署环境尚未配置Redis时沿用MySQL。

    key = f"ops:inventory:v1:{sku}"  # 当前演示为全部店铺；权限接入时加入授权范围。
    try:
        raw = redis_client.get(key)  # 相当于Redis命令GET key。
        if raw is not None:
            rows = inventory_rows.validate_json(raw, strict=True)
            if any(row.sku != sku for row in rows):
                raise ValueError("缓存商品与请求不一致")
            logger.info("[inventory.cache] hit sku=%s", sku)
            return [row.model_dump() for row in rows]
    except (RedisError, ValidationError, ValueError):
        logger.warning("[inventory.cache] read_failed_or_invalid; fallback=mysql")

    logger.info("[inventory.cache] miss sku=%s; source=mysql", sku)
    rows = find_inventory(sku)  # 未命中或缓存故障：执行原来的三表SQL。
    if rows:  # 当前只缓存查到的商品，空结果缓存放在穿透防护专项。
        try:
            redis_client.set(
                key,
                json.dumps(rows, ensure_ascii=False),  # Python列表转JSON文本。
                ex=CACHE_TTL_SECONDS,  # 写值时一起设置10秒有效期。
            )
        except RedisError:
            logger.warning("[inventory.cache] write_failed; returning_mysql_result")
    return rows
