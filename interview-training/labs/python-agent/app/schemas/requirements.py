from pydantic import BaseModel, ConfigDict, Field


class RequirementInput(BaseModel):
    """两个模型接口和消息预览接口共用的请求体格式。"""

    model_config = ConfigDict(
        strict=True,  # input必须是字符串。
        str_strip_whitespace=True,  # 去掉字符串首尾空白。
    )

    input: str = Field(min_length=1)  # 去掉空白后至少一个字符。



class RequirementResult(BaseModel):  # 描述模型必须返回的四个字段。
    model_config = ConfigDict(strict=True)  # 严格检查字段类型。

    action: str = Field(
        description="用户原文要求的唯一核心动作"
    )
    constraints: list[str] = Field(
        description="原文明确的限制，保留数字、频率、触发条件与审批要求"
    )
    entities: list[str] = Field(
        description="原文实际出现的关键对象"
    )
    missingInformation: list[str] = Field(
        max_length=3,  # 最多返回三个待确认问题。
        description="影响实现的待确认问题，最多3条；信息充分时为空数组",
    )
