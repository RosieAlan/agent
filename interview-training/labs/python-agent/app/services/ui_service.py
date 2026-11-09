from app.repositories.ad_repository import get_ad_report_from_db
from app.schemas.ui import (
    UIResponse,
    CardComponent,
    CardField,
    SelectionComponent,
    SelectionOption,
)


class AdReportNotFound(Exception):
    pass  # 接口层将它转换为404。


def build_ad_report_ui(
    user_id: str,
    store_id: str,
    campaign_id: str,
) -> UIResponse:
    report = get_ad_report_from_db(
        user_id,
        store_id,
        campaign_id,
    )  # 复用D07查询，继续检查店铺归属。

    if report is None:
        raise AdReportNotFound()

    spend = report["spend"]
    sales = report["attributed_sales"]
    currency = report["currency"]

    roas = (
        f"{sales / spend:.2f}"
        if spend > 0
        else "暂无：花费为0"
    )  # .2f表示显示两位小数；花费为0时避免除零。

    card = CardComponent(
        title=f"广告活动 {report['campaign_id']}",
        fields=[
            CardField(
                label="报表日期",
                value=report["report_date"],
            ),
            CardField(
                label="花费",
                value=f"{spend:.2f} {currency}",
            ),
            CardField(
                label="归因销售额",
                value=f"{sales:.2f} {currency}",
            ),
            CardField(
                label="ROAS",
                value=roas,
            ),
        ],
    )  # 创建卡片对象时，Pydantic立即检查字段。

    selection = SelectionComponent(
        title="接下来做什么？",
        options=[
            SelectionOption(
                id="generate_report",
                label="生成分析报告",
            ),
            SelectionOption(
                id="explain_metrics",
                label="查看指标说明",
            ),
        ],
    )  # 本块先返回选项，点击后的处理后续接入。

    return UIResponse(
        message=f"已查询广告报表。数据来源：{report['data_source']}。",
        components=[card, selection],
    )  # 合并成完整UI响应。