def check_low_stock(available: int, threshold: int) -> dict:
    is_low_stock = available < threshold
    return {
        "is_low_stock" : is_low_stock
    }
print(check_low_stock(6, 20))  # 调用函数并打印结果。这里完成判断和返回。