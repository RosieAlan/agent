from fastapi import FastAPI  # 创建Web应用和注册HTTP接口。
from pydantic import BaseModel, ConfigDict, Field  # 定义并执行数据校验。
from messages_demo import build_messages  # 从同目录文件导入已有函数。

app = FastAPI(title="电商Agent学习接口")  # 创建应用对象，启动服务器时加载它。


class RequirementInput(BaseModel):  # 描述请求JSON必须满足的规则。
    model_config = ConfigDict(
        strict=True,  # 严格校验类型，例如input传数字时拒绝。
        str_strip_whitespace=True,  # 校验长度前，去掉字符串首尾空白。
    )
    input: str = Field(min_length=1)  # 必填字符串，去空白后至少一个字符。


@app.post("/messages/preview")  # 注册POST接口，路径为/messages/preview。
def preview_messages(body: RequirementInput):  # 校验通过后，才执行这个函数。
    messages = build_messages(body.input)  # 用本次提交的需求组装消息。
    return {"messages": messages}  # FastAPI把字典编码为JSON响应。