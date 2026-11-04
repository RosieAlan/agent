from pydantic import BaseModel, ConfigDict, Field


class InventoryUpdateInput(BaseModel):
    model_config = ConfigDict(
        strict=True,  # 严格检查类型。
        extra="forbid",  # 拒绝未定义的字段。
    )

    stock: int = Field(
        ge=0,
        le=2_147_483_647,
    )  # 新库存数量，沿用数据库INTEGER范围。

    expected_version: int = Field(
        ge=1,
        le=2_147_483_646,
    )  # 新增：读取时的版本，为版本加1保留整数空间。
