# D06：定义工具并查看模型调用请求。日期：10/22

原课3.8.1-3.8.3普通函数、工具描述、bindTools、tool_calls；Python映射tool/args_schema/bind_tools。复用原函数，封装后保留浏览器直接查询；新增POST /ads/tool-request显示模型选择，执行及ToolMessage回传由下一块完成。框架外手动调度与有限循环继续D06。

本地版本core1.6.13核对tool签名及现有ChatOpenAI，官方models工具调用文档复核。新API先讲：@tool把函数包装成工具对象；第一个参数工具名，args_schema为Pydantic入参类，docstring为用途说明；bind_tools接收工具列表，返回带工具描述的模型调用对象，绑定时无远程请求；ainvoke时发送消息和工具Schema；response.tool_calls为模型提出的调用列表，含name/args/id；invalid_tool_calls解析失败转502。本轮Schema给模型参数说明，实际执行校验由工具invoke再次实施。绑定复用基础model，原structured_model继续。

## 文件一：ad_tools.py完整替换

```python
from langchain_core.tools import tool  # LangChain工具包装器。
from pydantic import BaseModel, ConfigDict, Field  # 复用已学的运行时校验。


def get_ad_report(campaign_id: str) -> dict:
    if campaign_id != "AD-DEMO-001":
        raise ValueError("未找到该广告活动的样例报表")
    return {
        "data_source": "synthetic_demo",  # 恢复独立的来源字段。
        "campaign_id": campaign_id,  # 恢复独立的编号字段。
        "report_date": "2026-10-21",
        "currency": "CNY",
        "spend": 100,
        "attributed_sales": 250,
        "clicks": 50,
        "impressions": 5000,
    }


class AdReportInput(BaseModel):  # 工具接收参数的格式。
    model_config = ConfigDict(strict=True, str_strip_whitespace=True)
    campaign_id: str = Field(
        min_length=1,
        description="广告活动编号，例如AD-DEMO-001",
    )


@tool("get_ad_report", args_schema=AdReportInput)
def ad_report_tool(campaign_id: str) -> dict:
    """查询指定广告活动的合成样例报表，返回花费、归因销售额、点击和展示。"""
    return get_ad_report(campaign_id)  # 真正执行时复用原查询函数。
```

## 文件二：llm_service.py末尾新增（model已在上方创建）

```python
from ad_tools import ad_report_tool  # 导入已包装的工具对象。

# 新增：把工具名、说明和参数格式附加到模型调用配置。
# 此处复用原始model，原structured_model继续服务需求抽取接口。
ad_tool_model = model.bind_tools([ad_report_tool])


async def request_ad_tool(input_text: str) -> dict:
    response = await ad_tool_model.ainvoke([
        {
            "role": "system",
            "content": (
                "你是广告报表助手。查询报表时使用get_ad_report工具。"
                "广告编号缺失时先询问编号；数据来源为合成样例。"
                "工具结果返回后才能据此描述花费或销售额。"
            ),
        },
        {"role": "user", "content": input_text},
    ])
    if response.invalid_tool_calls:  # 参数JSON等解析失败。
        raise OutputParserException("模型生成的工具参数无法解析")
    return {
        "content": response.content,  # 提出工具调用时可能为空。
        "tool_calls": response.tool_calls,  # 仅展示调用请求，执行由下一块接入。
    }
```

## 文件三：main.py新增导入

```python
from llm_service import request_ad_tool  # 新的模型工具选择函数。
```

## main.py末尾新增完整处理函数

```python
@app.post("/ads/tool-request")
async def ad_tool_request(body: RequirementInput):  # 沿用非空字符串入参校验。
    try:
        return await request_ad_tool(body.input)
    except APITimeoutError as error:
        raise HTTPException(status_code=504, detail="模型请求超时") from error
    except OutputParserException as error:
        raise HTTPException(status_code=502, detail="模型工具参数解析失败") from error
    except OpenAIError as error:
        raise HTTPException(status_code=502, detail="模型服务调用失败") from error
```

## 调用关系

启动：main导入llm_service→初始化基础model→导入ad_report_tool→bind_tools生成调用配置。请求：POST→main.ad_tool_request→llm_service.request_ad_tool→ad_tool_model.ainvoke→AIMessage→content/tool_calls JSON。本轮不会执行ad_report_tool/get_ad_report；旧GET查询入口继续直接调用普通函数。

## 新语法和参数含义

@tool是修饰其下函数的装饰器，创建工具对象ad_report_tool；其name=get_ad_report，description来自三引号函数说明，args_schema是AdReportInput类。与此前SYSTEM_PROMPT变量的多行文字相比，函数开头的三引号说明称docstring。tool_calls里name定位工具，args为参数字典，id用于下一块结果匹配。绑定提供Schema，执行时工具仍需校验模型给的实际参数；工具名相同于原函数名是显式命名，两个Python变量get_ad_report/ad_report_tool分别为普通函数与工具对象。

## 浏览器与检查

刷新8000/docs，POST /ads/tool-request输入{"input":"查询AD-DEMO-001的广告花费和归因销售额。"}。期望tool_calls包含name=get_ad_report、args.campaign_id=AD-DEMO-001、供应商生成的id；content可为空；这是教学期望，学生实际调用待交。再输入“查一下广告报表”时，模型可询问编号，tool_calls可为空；此时无工具可执行。绑定是否受供应商支持须以实际请求为准。本轮不强制tool_choice；后续非法参数、未知工具与轮次上限仍按D06实现。

必背：定义工具确定执行逻辑及入参；绑定工具把名称/描述/Schema提供给模型；模型生成tool_calls；后端校验执行，再回填ToolMessage。当前已讲定义/绑定/调用请求，实际执行回传下一块。

提交实际tool_calls并指出工具名、参数、调用编号。D06进行中，整体独立通过1/32、余31，原课独立分待测；D05延期缺口保留。

教师验证：真实LangChain工具参数校验、绑定Schema与解析器配合SDK固定返回；正常tool_calls、直接回答、无效参数JSON502、超时504、上游502、输入422均通过，数值/空白工具参数拒绝、未知活动失败；供应商调用0次，学生实际模型兼容性与运行待交。
