from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ReportQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile_id: str = Field(pattern=r"^[1-9][0-9]{0,19}$")
    start_date: date
    end_date: date
    campaign_id: str | None = Field(default=None, pattern=r"^[1-9][0-9]{0,19}$")
    attribution_window: Literal[1, 7, 14, 30] = 7  # 明确采用哪个归因窗口。
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=10000)

    @field_validator("profile_id", "campaign_id")
    @classmethod
    def valid_unsigned_id(cls, value):
        if value is not None and int(value) > 18446744073709551615:
            raise ValueError("编号超出源库BIGINT UNSIGNED范围")
        return value

    @model_validator(mode="after")
    def valid_date_range(self):
        if self.start_date > self.end_date:
            raise ValueError("开始日期应早于或等于结束日期")
        if (self.end_date - self.start_date).days >= 31:
            raise ValueError("单次查询最多31个自然日")
        return self


class AdProfile(BaseModel):
    profile_id: str  # 大整数编号用字符串返回，避免前端精度丢失。
    country: str | None
    currency: str | None
    timezone: str | None


class AdReportItem(BaseModel):
    campaign_id: str
    report_date: date
    current_campaign_name: str | None
    current_daily_budget: Decimal | None  # 活动表当前预算，与历史日报预算分别返回。
    report_campaign_budget: Decimal | None
    impressions: int | None
    clicks: int | None
    spend: Decimal | None  # JSON序列化为精确金额字符串。
    attributed_sales: Decimal | None
    attributed_orders: int | None
    attribution_record_present: bool  # 缺失归因行时，销售额保持null。


class AdMetrics(BaseModel):
    roas: Decimal | None  # 归因销售额 / 广告花费。
    ctr_percent: Decimal | None  # 点击量 / 展示量 * 100，单位为百分比。
    cpc: Decimal | None  # 广告花费 / 点击量，币种沿用账户币种。


class AdReportMetricsItem(AdReportItem):
    metrics: AdMetrics
    warnings: list[str]  # 指标缺失时的原因，供页面和后续Agent读取。


class AdReportResponse(BaseModel):
    data_source: Literal["company_test_readonly"] = "company_test_readonly"
    profile: AdProfile
    start_date: date
    end_date: date
    attribution_window: Literal[1, 7, 14, 30]
    items: list[AdReportMetricsItem]
    limit: int
    offset: int
    has_more: bool
    next_offset: int | None
