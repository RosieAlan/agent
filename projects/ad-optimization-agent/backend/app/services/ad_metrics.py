"""按广告活动的单日报表计算指标，保留缺失值及原始数据。"""

from decimal import Decimal, ROUND_HALF_UP


def _ratio(numerator, denominator, multiplier=Decimal("1")) -> Decimal | None:
    if numerator is None or denominator is None:
        return None  # 缺失数据保持未知。
    numerator, denominator = Decimal(str(numerator)), Decimal(str(denominator))
    if numerator < 0 or denominator <= 0:
        return None  # 分母为零或出现负数时，该指标无法计算。
    return (numerator / denominator * multiplier).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP,
    )  # 保留四位小数，金额计算使用十进制数。


def calculate_metrics(item: dict) -> dict:
    """接收一行原始报表，返回三个指标及无法计算的原因。"""
    has_attribution = item["attribution_record_present"]
    metrics = {
        "roas": _ratio(item["attributed_sales"], item["spend"]) if has_attribution else None,
        "ctr_percent": _ratio(item["clicks"], item["impressions"], Decimal("100")),
        "cpc": _ratio(item["spend"], item["clicks"]),
    }
    warnings = []
    if metrics["roas"] is None:
        warnings.append(
            "缺少归因记录，ROAS暂不可计算" if not has_attribution
            else "销售额缺失或为负数，或花费缺失、为零或为负数，ROAS暂不可计算"
        )
    if metrics["ctr_percent"] is None:
        warnings.append("点击量缺失或为负数，或展示量缺失、为零或为负数，点击率暂不可计算")
    if metrics["cpc"] is None:
        warnings.append("花费缺失或为负数，或点击量缺失、为零或为负数，CPC暂不可计算")
    return {"metrics": metrics, "warnings": warnings}


def add_report_metrics(report: dict) -> dict:
    return {
        **report,
        "items": [{**item, **calculate_metrics(item)} for item in report["items"]],
    }  # 创建新的返回对象，原始查询结果保持完整。
