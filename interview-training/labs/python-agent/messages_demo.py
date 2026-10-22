import json  # Python自带模块，用于生成JSON预览。


def build_messages(input_text: str) -> list[dict[str, str]]:
    return [  # 返回两条有顺序的消息。
        {
            "role": "system",
            "content": "你是电商运营需求助手。提取明确要求，缺失信息标为待确认。",
        },
        {
            "role": "user",
            "content": input_text,
        },
    ]


if __name__ == "__main__":  # 直接运行本文件时，执行下面的预览代码。
    input_text = "每天检查库存，库存低于20件时提醒运营人员"
    messages = build_messages(input_text)  # 调用消息组装函数。
    print(json.dumps(messages, ensure_ascii=False, indent=2))  # 打印JSON预览。