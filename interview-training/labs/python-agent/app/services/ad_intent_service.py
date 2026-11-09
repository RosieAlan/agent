from typing import Literal  # 限制字段只能使用指定值。
from pydantic import BaseModel, Field, ValidationError
from langchain_core.exceptions import OutputParserException
from app.services.llm_service import model  # 复用已有模型和本机配置。


class AdIntentResult(BaseModel):
    # 返回值只能是这三种意图之一。
    intent: Literal["query", "analyze", "chat"]

    # 简短说明分类依据，便于我们检查分类是否合理。
    reason: str = Field(min_length=1)


# 准备结构化调用对象；此时尚未请求模型。
intent_model = model.with_structured_output(
    AdIntentResult,
    method="function_calling",
)


async def classify_ad_intent(input_text: str) -> AdIntentResult:
    # input_text是接口收到的用户原文。
    messages = [
        {
            "role": "system",
            "content": (
                "你是电商运营助手的意图分类器。"
                "根据用户本次输入选择一种意图，并简短说明分类依据。"

                "query：获取已有数据、状态或已有报告。"
                "例如：查询广告花费、查看库存、获取分析报告。"

                "analyze：要求判断效果、解释原因、比较表现或给出建议。"
                "例如：分析广告表现、为什么转化下降、如何优化投放。"

                "chat：问候、感谢或普通闲聊。"

                "边界规则："
                "查询已有的分析报告属于query；"
                "要求重新分析并生成报告属于analyze；"
                "广告编号只用于确定对象，分类依据是用户要求执行的动作；"
                "同时要求查询数据和分析效果时选择analyze。"
                "信息不足且涉及业务任务时选择analyze，"
                "后续业务步骤继续澄清缺失信息。"
            ),
        },
        {
            "role": "user",
            "content": input_text,  # 把本次用户输入发给模型。
        },
    ]

    try:
        result = await intent_model.ainvoke(messages)  # 在这里请求模型。
    except ValidationError as error:
        # 将模型返回字段不符合Schema的情况交给接口统一处理。
        raise OutputParserException("意图分类结果格式错误") from error

    if not isinstance(result, AdIntentResult):
        raise OutputParserException("模型未返回有效的意图分类结果")

    return result  # 返回通过格式校验的分类对象。