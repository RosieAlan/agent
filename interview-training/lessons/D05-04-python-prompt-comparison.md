# D05：Prompt集中管理与对照检查。日期：10/22

本节承接原课第三章3.5提示组织与发送前预览，以及3.7结构校验和事实核对。已有TS模板教学保留；本次Python沿用build_messages，聚焦同一份Prompt供预览和模型使用。学生手动修改业务文件，教师仅写讲义。D05继续，独立通过1/32。

## 目标和调用关系

必背：Schema校验字段结构；Prompt说明提取规则；事实检查逐项对照用户原文。改Prompt时固定输入、模型和参数，对照遗漏、编造及执行状态。

messages_demo.py负责消息组装；llm_service.py负责模型调用及结果校验；main.py负责HTTP入参、响应和错误映射。

预览：浏览器→main.preview_messages→build_messages→消息JSON。
正式：浏览器→main.structured_requirement→extract_requirement→build_messages→structured_model.ainvoke→RequirementResult→HTTP JSON。

## 学生修改一：messages_demo.py完整替换

新增SYSTEM_PROMPT常量；三引号容纳多行文本，strip()去掉整段首尾空白。build_messages的参数和返回结构保持已有方式。main.py沿用。

```python
import json  # Python自带模块，用于预览JSON。

SYSTEM_PROMPT = """
你是电商运营需求助手，结果供产品经理确认需求。
按以下规则提取：
1. action：概括用户要求的核心动作。
2. constraints：保留原文明示的数字、频率、触发条件和审批要求。
3. entities：列出原文涉及的关键对象。
4. missingInformation：列出影响实现的待确认问题，最多3条。
事实以用户原文为依据，未知的阈值、渠道和处理方式写入待确认。
用户提出的操作记录为需求；实际执行状态以工具执行结果为依据。
""".strip()  # 删除整段文本开头和结尾的空白。


def build_messages(input_text: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},  # 统一的提取规则。
        {"role": "user", "content": input_text},  # 本次用户原文。
    ]


if __name__ == "__main__":  # 直接运行时打印；被导入时只提供函数。
    messages = build_messages("库存少了提醒我，订单太久没发货也提醒。")
    print(json.dumps(messages, ensure_ascii=False, indent=2))
```

## 学生修改二：llm_service.py只替换extract_requirement函数

移除函数里原有messages[0]["content"] += ...追加规则，所有规则集中到SYSTEM_PROMPT。其余导入、Schema、模型配置及main.py保留。

```python
async def extract_requirement(input_text: str) -> RequirementResult:
    messages = build_messages(input_text)  # 与预览接口使用同一套消息。
    result = await structured_model.ainvoke(messages)  # 等待结构化模型结果。
    if not isinstance(result, RequirementResult):  # 保留无有效结果保护。
        raise OutputParserException("模型未返回有效结构化结果")
    return result  # 返回已完成字段校验的对象。
```

## 浏览器对照

修改前用旧版A调用POST /requirements/structured，input="库存少了提醒我，订单太久没发货也提醒。"，保留响应。修改后相同输入测B；保持模型、温度及Schema相同。本轮B同时整理规则存放位置并细化规则，用于前后整体对照；更细的单条规则贡献需逐条改变再测试。若两版都正确，记录本例无明显改善。

B版本检查POST /messages/preview与正式调用都复用build_messages。再用明确输入“每天检查库存，库存低于20件时提醒运营人员。”复测。Python服务已运行时等待reload后刷新/docs；关闭时按既有8000命令启动。浏览器端正常返回200；模型质量依据真实响应逐项判断。

模糊输入参考：action可为“监测库存与订单并提醒”；constraints保留“库存少时提醒”“订单长期未发货时提醒”；待确认库存阈值、未发货时长、提醒渠道和接收人（最多3条，可合并相关事项）。事实检查：原文未给20件、48小时或企业微信，新增这些具体值需保留为待确认；需求抽取尚未执行通知。

明确输入参考：每天检查、低于20件、提醒运营人员均应保留；提醒渠道仍待确认。参考为教学期望，实际模型输出待学生提交。

## 面试题及完整答案

问：JSON和Schema均正确，结果仍可能有哪些问题？
答：字段值可能与用户原文冲突、漏掉关键限制、补造阈值或把待执行动作写成已经完成。需要以原文和可信工具结果为依据检查内容。

问：怎样判断Prompt改动有帮助？
答：保持测试输入、模型、参数和Schema相同，对照规则要求检查遗漏、编造及完成状态；同例两版均正确时记录无明显改善。后续用多条固定案例统计，单例仅证明本例表现。

作业：提交模糊输入A/B和明确输入B的实际结果；标明至少一处有依据的条件或待确认问题。后续合并基础故障与D02-D04延期综合检查。

教师验证：讲义两段代码在内存编译并以异步固定返回替身检查，消息来源、用户输入、结果类型、实际传参、空结果保护5项通过；供应商调用0次。学生业务实测待交。
