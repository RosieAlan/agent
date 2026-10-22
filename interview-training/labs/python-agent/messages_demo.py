import json  # 导入 Python 自带的 JSON 模块，用于把数据转为 JSON 文本。


def build_messages(input_text: str) -> list[dict[str, str]]:
    # 返回一个列表：每个字典保存一条消息，列表顺序就是消息顺序。
    return [
        {
            "role": "system",  # 系统消息：规定模型的任务与要求。
            "content": "你是电商运营需求助手。提取明确要求，缺失信息标为待确认。",
        },
        {
            "role": "user",  # 用户消息：保存本次用户提交的具体内容。
            "content": input_text,
        },
    ]


# 准备本次业务输入。
input_text = "每天检查库存，库存低于20件时提醒运营人员"

# 调用函数，取得组装好的两条消息。
messages = build_messages(input_text)

# 把列表转为便于阅读的 JSON 文本：
# ensure_ascii=False 保留中文；indent=2 使用两个空格排版。
preview = json.dumps(messages, ensure_ascii=False, indent=2)

print(preview)  # 展示消息预览；真实模型请求会在后续单独加入。