def check_low_stock(available: int, threshold: int) -> dict:
    is_low_stock = available < threshold

    gap = max(threshold - available, 0)
    return {"is_low_stock": is_low_stock, "gap_to_threshold": gap}


inventories = [
    {"store_name": "广州演示店", "available": 28},
    {"store_name": "深圳演示店", "available": 6},
]
items = []

for inventory in inventories:
    print(inventory)
    result = check_low_stock(inventory["available"], 20)
    items.append(
        {
            "store_name": inventory["store_name"],  # 当前店铺名称。
            "available": inventory["available"],  # 当前可售数量。
            "is_low_stock": result["is_low_stock"],  # 从判断结果里取出是否低库存。
            "gap_to_threshold": result["gap_to_threshold"],  # 从判断结果里取出缺口数量。
        }
    )
    print(items)  # 循环全部结束后，打印完整列表。
