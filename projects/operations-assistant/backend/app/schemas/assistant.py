from pydantic import BaseModel, ConfigDict, Field


class AssistantInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    input: str = Field(min_length=1, max_length=1000)


class AssistantOutput(BaseModel):
    answer: str
    data_source: str
    tool_results: list[dict]
