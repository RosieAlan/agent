from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo('Asia/Shanghai')


def next_daily_run(daily_time: str, now: datetime) -> datetime:
    """输入与返回均为 UTC；业务时间固定为上海时区。"""
    local = now.replace(tzinfo=timezone.utc).astimezone(SHANGHAI)
    hour, minute = map(int, daily_time.split(':'))
    target = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= local:
        target += timedelta(days=1)
    return target.astimezone(timezone.utc).replace(tzinfo=None)


def build_report(items: list[dict], threshold: int, now: datetime) -> dict:
    snapshot = [{**item, 'is_low_stock': item['available'] < threshold,
                 'gap_to_threshold': max(0, threshold - item['available'])} for item in items]
    low = sum(item['is_low_stock'] for item in snapshot)
    return {'summary': f'已检查 {len(snapshot)} 条店铺库存，发现 {low} 条低库存。',
            'items': snapshot, 'low_stock_count': low, 'total_items': len(snapshot),
            'report_date': now.replace(tzinfo=timezone.utc).astimezone(SHANGHAI).date().isoformat(),
            'data_source': 'synthetic_demo', 'threshold': threshold}
