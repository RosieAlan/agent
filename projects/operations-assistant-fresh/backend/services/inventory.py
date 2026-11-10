from services.inventory_cache import find_inventory_cached


def inspect_inventory(sku: str, threshold: int, *, fresh: bool = False) -> dict:
    """查询库存，并根据本次阈值检查各店铺。"""

    inventories = find_inventory_cached(sku, fresh=fresh)  # fresh=True时本次直接查MySQL。
    items = []
    low_stock_count = 0

    for inventory in inventories:  # 依次处理广州店、深圳店等记录。
        available = inventory["available"]
        is_low_stock = available < threshold

        if is_low_stock:
            low_stock_count += 1  # 累计异常店铺数量。

        items.append({
            **inventory,  # 复制原记录里的商品、店铺和库存字段。
            "is_low_stock": is_low_stock,
            "gap_to_threshold": max(threshold - available, 0),
        })  # 追加到本次检查结果。

    return {
        "data_source": "synthetic_demo",
        "sku": sku,
        "threshold": threshold,
        "low_stock_count": low_stock_count,
        "items": items,
    }
