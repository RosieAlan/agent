from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ReplenishmentInput(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    sku: str = Field(min_length=1, max_length=64)
    store_code: str = Field(min_length=1, max_length=64)

    daily_sales: Decimal = Field(
        ge=0,
        le=1_000_000,
        max_digits=12,
        decimal_places=4,
        allow_inf_nan=False,
    )  # 日均销量：允许小数，拒绝负数和无穷值。

    lead_days: int = Field(
        strict=True, ge=1, le=365,
    )  # 采购到货周期，单位：天。

    safety_stock: int = Field(
        strict=True, ge=0, le=1_000_000,
    )  # 安全库存，单位：件。

    available: int = Field(
        strict=True, ge=0, le=1_000_000,
    )  # 当前可售数量。

    eligible_inbound: int = Field(
        strict=True, ge=0, le=1_000_000,
    )  # 本周期内已确认可用的在途数量。

    pack_size: int = Field(
        default=1, strict=True, ge=1, le=1_000_000,
    )  # 每箱数量，按整箱采购。


class ReplenishmentResult(BaseModel):
    data_source: Literal["manual_demo"] = "manual_demo"
    policy_version: Literal["demo-leadtime-v1"] = "demo-leadtime-v1"
    status: Literal["draft"] = "draft"  # 当前结果为待确认草案。

    sku: str
    store_code: str
    target_stock: int = Field(ge=0)
    shortage: int = Field(ge=0)
    order_quantity: int = Field(ge=0)
    limitation: str  # 说明当前规则的适用限制。