# D05 Python消息预览接口与请求校验

2026-10-22，D05继续。原课程第一章消息结构、第三章3.2后端承载及Schema校验；迁移到Python/FastAPI。必备：请求体校验、严格字符串、去空白后非空、模块导入与main保护。熟练：虚拟环境、Uvicorn启动、浏览器/docs使用。当前仅预览messages，本课模型请求0次，输出抽取及事实验证后续继续。

学生已提交messages_demo.py库存条件版本，system/user角色与输入保留正确，运行及独立业务输入修改通过。当前任务修改该文件底部，加入__name__保护；新增main.py接受POST /messages/preview。原Nest和浏览器保持原状；Python8000使用独立/docs页面。

## messages_demo.py完整候选

```python
import json  # Python自带模块，用于生成JSON预览。


def build_messages(input_text: str) -> list[dict[str, str]]:
    return [  # 两条有顺序的消息。
        {
            "role": "system",
            "content": "你是电商运营需求助手。提取明确要求，缺失信息标为待确认。",
        },
        {"role": "user", "content": input_text},
    ]


if __name__ == "__main__":  # 直接运行本文件时执行；其他文件导入时跳过本段。
    input_text = "每天检查库存，库存低于20件时提醒运营人员"
    messages = build_messages(input_text)  # 调用可复用函数。
    print(json.dumps(messages, ensure_ascii=False, indent=2))  # 本地预览。
```

## main.py完整候选

```python
from fastapi import FastAPI  # 创建Web应用和注册HTTP接口。
from pydantic import BaseModel, ConfigDict, Field  # 定义并执行数据校验。
from messages_demo import build_messages  # 从同目录文件导入已有函数。

app = FastAPI(title="电商Agent学习接口")  # Uvicorn启动时加载这个应用对象。


class RequirementInput(BaseModel):  # 描述请求JSON必须满足的规则。
    model_config = ConfigDict(
        strict=True,  # 按声明的类型严格校验。
        str_strip_whitespace=True,  # 校验长度前，去掉字符串首尾空白。
    )
    input: str = Field(min_length=1)  # input必填；去掉空白后至少一个字符。


@app.post("/messages/preview")  # 把POST路径关联到下面的函数。
def preview_messages(body: RequirementInput):  # FastAPI先校验JSON，再传入body对象。
    messages = build_messages(body.input)  # 读取通过校验的字符串，复用已有消息构建。
    return {"messages": messages}  # FastAPI将字典编码为HTTP JSON响应。
```

## 启动与验收

Python3.11.9；已检测全局FastAPI0.128.0、Pydantic2.12.5、Uvicorn0.40.0和HTTPX0.28.1。学生创建专用.venv后安装这三个已核对的版本，通过.venv/Scripts/python.exe调用，依赖记录与锁定后续结合交付继续。命令直接在对话交付；激活脚本可省略，避免PowerShell执行策略问题。Uvicorn启动main:app，host127.0.0.1，port8000，浏览器http://127.0.0.1:8000/docs点POST /messages/preview、Try it out、Execute。

正常及首尾空白返回200，数字、空串、全空白、缺失字段返回422且业务函数不执行。JSON本身格式错误也由框架拒绝，错误细节按实际版本展示；原Nest400/201与本节FastAPI422/200各遵循当前显式配置。

必背：FastAPI根据路由找到处理函数，使用Pydantic校验请求体；合法数据进入函数，返回字典由框架编码为JSON。Pydantic校验数据格式与约束，事实正确性依据输入与业务数据另行核对。

面试题答案：数字输入被Pydantic拒绝；__name__保护让导入时仅加载函数定义；str是类型提示，BaseModel负责运行时校验；return字典保持框架可处理的结构化数据，JSON编码交给FastAPI。独立检查提交正常200、空白422、数字422三组浏览器结果，指出错误字段input。
