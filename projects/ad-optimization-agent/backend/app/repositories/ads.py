from sqlalchemy import text

from app.db.source import source_engine
from app.schemas.ads import ReportQuery

PROFILE_FIELDS = "CAST(id AS CHAR) AS profile_id,countryCode AS country,currencyCode AS currency,timezone"
ATTRIBUTION_COLUMNS = {
    1: ("attributedSales1d", "attributedConversions1d"),
    7: ("attributedSales7d", "attributedConversions7d"),
    14: ("attributedSales14d", "attributedConversions14d"),
    30: ("attributedSales30d", "attributedConversions30d"),
}  # SQL列名从固定白名单取，查询值继续参数绑定。


def list_profiles(limit: int) -> list[dict]:
    with source_engine.connect() as connection:
        rows = connection.execute(text(
            f"SELECT {PROFILE_FIELDS} FROM t_amz_adv_profile ORDER BY id LIMIT :limit"
        ), {"limit": limit}).mappings().all()
        return [dict(row) for row in rows]


def fetch_campaign_budget(profile_id: str, campaign_id: str) -> dict | None:
    with source_engine.connect() as connection:
        row = connection.execute(text("""
            SELECT c.dailyBudget AS source_budget,p.currencyCode AS currency
            FROM t_amz_adv_campaigns c JOIN t_amz_adv_profile p ON p.id=c.profileid
            WHERE c.profileid=:profile_id AND c.campaignId=:campaign_id LIMIT 1
        """), {"profile_id": profile_id, "campaign_id": campaign_id}).mappings().first()
        return dict(row) if row is not None else None  # 只读获取当前测试库中的预算快照。


def fetch_reports(query: ReportQuery) -> dict | None:
    sales_column, orders_column = ATTRIBUTION_COLUMNS[query.attribution_window]
    with source_engine.connect() as connection:
        profile = connection.execute(text(
            f"SELECT {PROFILE_FIELDS} FROM t_amz_adv_profile WHERE id=:profile_id LIMIT 1"
        ), {"profile_id": query.profile_id}).mappings().first()
        if profile is None:
            return None
        campaign_filter = "AND r.campaignId=:campaign_id" if query.campaign_id else ""
        statement = text(f"""
            SELECT CAST(r.campaignId AS CHAR) AS campaign_id,r.bydate AS report_date,
              c.name AS current_campaign_name,c.dailyBudget AS current_daily_budget,
              r.campaignBudget AS report_campaign_budget,r.impressions,r.clicks,r.cost AS spend,
              a.{sales_column} AS attributed_sales,a.{orders_column} AS attributed_orders,
              (a.campaignId IS NOT NULL) AS attribution_record_present
            FROM t_amz_adv_rpt2_sp_compaigns r
            LEFT JOIN t_amz_adv_campaigns c
              ON c.campaignId=r.campaignId AND c.profileid=r.profileid
            LEFT JOIN t_amz_adv_rpt2_sp_compaigns_attributed a
              ON a.campaignId=r.campaignId AND a.bydate=r.bydate
            WHERE r.profileid=:profile_id AND r.bydate BETWEEN :start_date AND :end_date
              {campaign_filter}
            ORDER BY r.bydate DESC,r.campaignId DESC
            LIMIT :row_limit OFFSET :offset
        """)
        params = {**query.model_dump(), "row_limit": query.limit + 1}
        rows = connection.execute(statement, params).mappings().all()
        has_more = len(rows) > query.limit  # 多查一条判断下一页，避免全量COUNT。
        return {
            "profile": dict(profile),
            "start_date": query.start_date, "end_date": query.end_date,
            "attribution_window": query.attribution_window,
            "items": [dict(row) for row in rows[:query.limit]],
            "limit": query.limit, "offset": query.offset,
            "has_more": has_more,
            "next_offset": query.offset + query.limit if has_more else None,
        }
