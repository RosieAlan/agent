import json  # Python自带模块，用于打印JSON预览。

# 新增：集中保存系统提示词，预览和正式请求共同使用。
SYSTEM_PROMPT = """
你是电商运营需求助手，结果供产品经理确认需求。

按以下规则提取：
1. action：概括用户要求的核心动作。
2. constraints：保留原文明示的数字、频率、触发条件和审批要求。
3. entities：列出原文涉及的关键对象。
4. missingInformation：列出影响实现的待确认问题，最多3条。

事实以用户原文为依据，未知的阈值、渠道和处理方式写入待确认。
用户提出的操作记录为需求；实际执行状态以工具执行结果为依据。
涉及审批时，分别提取审批前置要求、执行主体和执行方式。
原文未明确由谁执行、如何执行时，将其列为待确认，保留原文授权范围。
""".strip()  # 去掉整段文本首尾的空白。


def build_messages(input_text: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,  # 修改：直接使用集中保存的规则。
        },
        {
            "role": "user",
            "content": input_text,  # 沿用：本次用户输入。
        },
    ]


if __name__ == "__main__":  # 直接运行本文件时执行预览。
    messages = build_messages(
        "库存少了提醒我，订单太久没发货也提醒。"
    )
    print(json.dumps(messages, ensure_ascii=False, indent=2))
