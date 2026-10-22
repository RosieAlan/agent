# D06：工具定义、执行与结果回传。日期：10/22（提前进入）

用户明确要求直接进入D06，D05验收待补保持原记录，独立通过1/32。原课第三章3.8.1至3.8.5与第四章4.3，按普通函数→手动闭环→LangChain包装/绑定→工具失败与上限教学，完整范围继续。第一块先实现可通过浏览器直接验证的业务查询函数；模型工具调用、手动循环与计算工具在后续同单元落实。

## 概念与目标

工具由可执行函数和名称/说明/参数Schema等信息组成。get_ad_report接收campaign_id，返回报表或明确失败；模型生成tool_calls表达调用工具与参数，后端校验后执行，再用ToolMessage回传，模型根据结果答复。绑定工具时提供可选工具说明；本轮只实现可执行函数与HTTP验证，模型绑定尚未接入。

## 文件职责

新增ad_tools.py：执行查询。main.py增加import和GET处理函数。llm_service.py/messages_demo.py沿用。浏览器GET /ads/report/AD-DEMO-001→main.ad_report(campaign_id)→ad_tools.get_ad_report(campaign_id)→dict→HTTP JSON。未知编号ValueError沿调用栈回到main，转换404。

数据为自建合成样例，真实HTTP本地服务与真实外部广告数据分别记录。当前无领星授权/API调用。

## 新建ad_tools.py完整代码

```python
def get_ad_report(campaign_id: str) -> dict:
    # 本轮只提供一个明确标记的样例广告活动。
    if campaign_id != "AD-DEMO-001":
        raise ValueError("未找到该广告活动的样例报表")

    # 返回可供浏览器和后续模型工具共同使用的数据。
    return {
        "data_source": "synthetic_demo",  # 自建合成数据。
        "campaign_id": campaign_id,  # 查询的广告活动编号。
        "report_date": "2026-10-21",  # 样例统计日期。
        "currency": "CNY",  # 金额单位：人民币元。
        "spend": 100,  # 广告花费。
        "attributed_sales": 250,  # 按样例归因规则计入的销售额。
        "clicks": 50,  # 点击次数。
        "impressions": 5000,  # 展示次数。
    }
```

## main.py顶部新增导入

```python
from ad_tools import get_ad_report  # 导入新文件中的查询函数。
```

## main.py在app创建之后新增完整函数（可放文件末尾）

```python
@app.get("/ads/report/{campaign_id}")  # GET读取数据，花括号标记路径参数。
def ad_report(campaign_id: str):
    try:
        return get_ad_report(campaign_id)  # 编号传入查询函数，字典作为响应。
    except ValueError as error:
        # HTTPException已由main.py原有代码导入。
        raise HTTPException(status_code=404, detail=str(error)) from error
```

新语法：-> dict为返回类型提示，运行时字段校验后续按Schema完善；!=判断编号不相等；raise ValueError抛出查询失败；app.get注册读取路由；{campaign_id}的同名路径值自动传入函数；str(error)生成异常文字。导入时定义函数，请求到来时执行查询。同步函数只读固定本地数据，本轮无await；后续网络查询使用异步客户端。

## 浏览器验证

服务开着时等待reload。关闭时在python-agent目录用.venv Python启动uvicorn main:app --reload --host 127.0.0.1 --port 8000。打开http://127.0.0.1:8000/ads/report/AD-DEMO-001应返回样例报表；改成AD-DEMO-999应返回404，detail未找到样例。直接浏览器地址栏访问，无需Body。供应商调用0次。

## 必背和检查

工具提供明确输入、执行逻辑和结果；模型负责提出工具调用，后端负责校验及执行，工具结果回填后模型才能据此回答。本例输入campaign_id，输出dict报表，未知编号抛ValueError，由HTTP入口转换404。

学生提交浏览器正常和未知编号结果，并解释由哪个文件真正查数据。下一块定义工具名称/描述/参数Schema，再手动执行调用与回传；bind_tools先解释后使用。

教师验证：本地FastAPI TestClient五项检查通过（200、合成标签、报表数值、404、OpenAPI路径），供应商请求0次；学生浏览器运行待交。
