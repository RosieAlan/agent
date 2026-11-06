from pydantic import BaseModel, ConfigDict, Field


class AssistantInput(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,  # 去掉输入两端空白。
        extra="forbid",             # 拒绝未定义的字段。
    )

    input: str = Field(min_length=1, max_length=1000)


class ToolPlanResponse(BaseModel):
    content: str
    tool_calls: list[dict]