from sqlalchemy import select, text  # ORM查询、SQL文本。
from sqlalchemy.orm import Session  # 管理本次数据库操作。

from app.db.session import engine  # 复用已有连接池。
from app.db.models import AdReport, Store  # 广告报表模型、店铺模型。


def initialize_ad_demo() -> None:
    """手动初始化两家店的合成广告报表。"""

    with engine.begin() as connection:
        # 两条样例一起提交；发生错误时一起回滚。

        connection.execute(text("""
            INSERT INTO ad_reports
                (id, store_id, campaign_id, report_date, currency,
                 spend, attributed_sales, clicks, impressions, data_source)
            VALUES
                ('ad-A-20261021', 'store-A', 'AD-DEMO-001', '2026-10-21',
                 'CNY', 100, 250, 50, 5000, 'synthetic_demo'),

                ('ad-B-20261021', 'store-B', 'AD-DEMO-001', '2026-10-21',
                 'CNY', 900, 1800, 100, 8000, 'synthetic_demo')

            ON CONFLICT (store_id, campaign_id, report_date) DO NOTHING
        """))
        # 相同店铺、活动、日期已经存在时，保留原来的数据。
        # 重复运行初始化，也会保留你后来修改过的花费。


def get_ad_report_from_db(
    user_id: str,
    store_id: str,
    campaign_id: str,
) -> dict | None:
    """查询当前用户所属店铺中，该广告最近一期的报表。"""

    with Session(engine) as session:
        # 本次查询结束后，Session关闭并归还连接。

        statement = (
            select(AdReport)  # 准备读取广告报表。
            .join(
                Store,
                Store.id == AdReport.store_id,
            )  # 根据店铺编号，关联店铺和报表。

            .where(
                Store.user_id == user_id,  # 核对店铺属于当前用户。
                AdReport.store_id == store_id,  # 限定当前店铺。
                AdReport.campaign_id == campaign_id,  # 限定广告活动。
            )

            .order_by(
                AdReport.report_date.desc()
            )  # 报表日期从新到旧排列。

            .limit(1)  # 只读取最近一期。
        )

        report = session.scalars(statement).one_or_none()
        # 到这里才真正执行SQL。
        # 找到返回报表对象，没找到返回None。

        if report is None:
            return None

        return {
            "data_source": report.data_source,
            "store_id": report.store_id,
            "campaign_id": report.campaign_id,

            "report_date": report.report_date.isoformat(),
            # 日期对象转成"2026-10-21"这样的文本。

            "currency": report.currency,

            "spend": float(report.spend),
            "attributed_sales": float(report.attributed_sales),
            # 维持原工具返回JSON数字的格式，供展示和比率计算使用。
            # 金额结算应继续使用Decimal或整数分。

            "clicks": report.clicks,
            "impressions": report.impressions,
        }


if __name__ == "__main__":
    initialize_ad_demo()  # 直接运行本文件时初始化；import时跳过。
    print("广告合成样例已准备好；已有报表保持原值")
