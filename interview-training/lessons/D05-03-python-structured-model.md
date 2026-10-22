# D05 Python真实模型调用与结构化接口

2026-10-22，原课第三章3.7.1至3.7.3与第二章配置/服务分层。学生请求体数字输入实测422，loc=body/input，检查通过；正常和空白案例仅口述已完成，保留待阶段抽检。4001/3002已关闭，当前仅Python8000/docs。Python正式模型请求由学生执行。

## 本块目的与改动

新增llm_service.py：环境读取、结果Schema、ChatOpenAI及结构化异步调用；修改main.py：保留预览，增加POST /requirements/structured与错误映射。messages_demo.py沿用。Python命名with_structured_output/ainvoke分别对应原TS的withStructuredOutput/异步invoke。Pydantic类作为schema参数时，LangChain解析并校验结果，返回RequirementResult对象。函数调用协议用于生成结构化字段，外部业务工具执行留D06。

局部.env沿用原项目个人模型服务的API Key、Base URL和模型名称，由学生在本机填写；不要提交或贴出密钥。ChatOpenAI此处走已核对的Chat Completions兼容接口，use_responses_api=False，method=function_calling；第三方需支持tools/tool_choice，扩展响应字段不视为兼容保证。变更.env后手动重启，避免误认为reload会自动加载.env。

## llm_service.py完整候选

```python
import os  # 读取进程环境变量。
from pathlib import Path  # 定位当前文件同目录下的.env。
from dotenv import load_dotenv  # 从本地.env加载配置。
from langchain_openai import ChatOpenAI  # LangChain的模型调用组件。
from langchain_core.exceptions import OutputParserException  # 将无有效结果归入解析失败。
from pydantic import BaseModel, ConfigDict, Field  # 规定并校验模型结果。
from messages_demo import build_messages  # 复用已经学过的消息组装函数。

load_dotenv(Path(__file__).with_name(".env"))  # 默认保留进程中已有环境变量。


class RequirementResult(BaseModel):  # 固定模型输出字段；全部字段必填。
    model_config = ConfigDict(strict=True)  # 严格检查返回字段类型。
    action: str = Field(description="用户原文要求的唯一核心动作")
    constraints: list[str] = Field(description="原文明确的限制，保留数字、频率、触发条件与审批要求")
    entities: list[str] = Field(description="原文实际出现的关键对象")
    missingInformation: list[str] = Field(
        max_length=3, description="影响实现的待确认问题，最多3条；信息充分时为空数组"
    )


model = ChatOpenAI(  # 创建可复用的模型调用对象；此时尚未发送请求。
    model=os.environ["OPENAI_MODEL"],  # 与原Nest项目使用相同模型名。
    api_key=os.environ["OPENAI_API_KEY"],  # 密钥只在后端读取。
    base_url=os.environ["OPENAI_BASE_URL"],  # 使用原项目的完整接口基础地址。
    temperature=0,  # 降低采样随机性，输出仍需验收。
    timeout=30,  # HTTP超时配置，单位秒。
    max_retries=0,  # 本块失败直接返回，方便定位第一处错误。
    use_responses_api=False,  # 显式使用Chat Completions接口。
)

structured_model = model.with_structured_output(
    RequirementResult, method="function_calling"  # 通过工具调用协议声明输出结构。
)


async def extract_requirement(input_text: str) -> RequirementResult:
    messages = build_messages(input_text)  # 使用当前请求中的需求字符串。
    messages[0]["content"] += (
        "已知事实须有用户原文依据；数值、频率、触发条件与审批要求完整保留。"
        "未知内容写入待确认问题，最多3条。用户提出的操作要求记为待执行需求。"
    )
    result = await structured_model.ainvoke(messages)  # 发起异步模型请求并等待校验后的对象。
    if not isinstance(result, RequirementResult):  # 防止空结果进入HTTP响应。
        raise OutputParserException("模型未返回有效结构化结果")
    return result  # 返回RequirementResult，供接口返回给浏览器。
```

## main.py完整候选

```python
from fastapi import FastAPI, HTTPException  # 应用、路由和可控HTTP错误。
from langchain_core.exceptions import OutputParserException  # 模型结果解析失败。
from openai import APITimeoutError, OpenAIError  # SDK请求超时及上游调用错误。
from pydantic import BaseModel, ConfigDict, Field, ValidationError  # 请求及结果校验。
from messages_demo import build_messages  # 原消息预览函数。
from llm_service import RequirementResult, extract_requirement  # 导入后端模型能力。

app = FastAPI(title="电商Agent学习接口")


class RequirementInput(BaseModel):  # 沿用已验证的请求体规则。
    model_config = ConfigDict(strict=True, str_strip_whitespace=True)
    input: str = Field(min_length=1)


@app.post("/messages/preview")  # 保留原预览接口。
def preview_messages(body: RequirementInput):
    return {"messages": build_messages(body.input)}


@app.post("/requirements/structured", response_model=RequirementResult)
async def structured_requirement(body: RequirementInput):  # 等待模型时允许事件循环处理其他请求。
    try:
        return await extract_requirement(body.input)  # 返回经过结构校验的模型结果。
    except APITimeoutError as error:
        raise HTTPException(status_code=504, detail="模型请求超时，请稍后重试") from error
    except (ValidationError, OutputParserException) as error:
        raise HTTPException(status_code=502, detail="模型返回的数据未通过结构校验") from error
    except OpenAIError as error:
        raise HTTPException(status_code=502, detail="模型服务调用失败，请检查后端配置及服务状态") from error
```

## 配置占位示例

```dotenv
OPENAI_API_KEY=填写原项目的个人模型API密钥
OPENAI_BASE_URL=填写原项目的OPENAI_BASE_URL完整值
OPENAI_MODEL=填写原项目config/langchain.yaml中llm.model的值
```

占位内容需替换。密钥和地址从原Nest本地.env查找，模型从原config/langchain.yaml查找；不要覆盖原文件。KeyError说明缺失环境变量，启动阶段失败；401/403/404/429等上游错误经本课API统一502，需后端分型定位，后续观测任务补齐脱敏日志及关联编号。SDK HTTP timeout与整次任务期限分别讨论；客户端断开取消/限流等D04能力在后续Python迁移继续验收。

浏览器/docs点POST /requirements/structured：提交库存低于20件提醒原句；预期200且action/constraints/entities/missingInformation齐全，字段事实与原文核对。数字与空白继续422且不发模型请求。报表尚未接入，本接口抽取需求，实际库存事实与通知执行需工具证据。

必背：Prompt规定任务和事实规则；Pydantic Schema描述并校验字段；with_structured_output指定结构化生成与解析；ainvoke实际发请求；类型校验通过后仍核对原文事实。async def定义异步函数，await等待异步操作；配合非阻塞客户端让事件循环在等待网络期间处理其他任务，CPU密集工作另做安排。

面试答案：字段类型正确仍可能事实错误；with_structured_output返回配置后的可调用对象，ainvoke阶段发送请求；用户input不合法由框架422，供应商失败为上游502、超时504，Schema失败502。独立检查：业务改为“每天检查订单，超过48小时未发货时提醒运营”，提交结果并核对每天/48小时/未发货条件；不得填充已通知等无执行依据事实。当前代码为教师候选，学生复制与真实模型结果待验收。
