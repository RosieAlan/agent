from pydantic import BaseModel, ConfigDict, Field


class ConversationInput(BaseModel):
    model_config = ConfigDict(
        strict=True,
        str_strip_whitespace=True,
        extra="forbid",
    )

    title: str = Field(
        min_length=1,
        max_length=100,
    )  # 创建会话时提交标题。