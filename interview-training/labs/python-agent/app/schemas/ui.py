from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field


class UIModel(BaseModel):
    model_config = ConfigDict(
        strict=True,
        extra="forbid",
    )  # 下面的模型继承这套严格校验规则。


class CardField(UIModel):
    label: str = Field(min_length=1)  # 字段名称，例如“花费”。
    value: str  # 展示文字，例如“100.00 CNY”。


class CardComponent(UIModel):
    type: Literal["card"] = "card"  # 固定为卡片类型。
    title: str = Field(min_length=1)
    fields: list[CardField] = Field(
        min_length=1,
        max_length=20,
    )  # 卡片至少包含一个字段。


class SelectionOption(UIModel):
    id: str = Field(min_length=1)  # 后端识别的选项编号。
    label: str = Field(min_length=1)  # 用户看到的文字。


class SelectionComponent(UIModel):
    type: Literal["selection"] = "selection"
    title: str = Field(min_length=1)
    options: list[SelectionOption] = Field(
        min_length=1,
        max_length=10,
    )
    allowMultiple: bool = False  # 与已有前端协议保持一致。


UIComponent = Annotated[
    CardComponent | SelectionComponent,  # 当前支持两种组件。
    Field(discriminator="type"),  # 根据type选择检查规则。
]


class UIResponse(UIModel):
    version: Literal["1.0"] = "1.0"  # 当前协议版本。
    message: str = Field(min_length=1)
    components: list[UIComponent] = Field(
        min_length=1,
        max_length=10,
    )  # 一次响应可以组合多个组件。