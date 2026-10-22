# D06：执行工具、回填结果、生成最终答复。日期：10/22

学生实际返回tool_calls包含get_ad_report、campaign_id=AD-DEMO-001、call_8e660b5c6c45486d89fc14dc，工具选择/参数生成通过；content同时存在文字属于允许形式，实际执行待本块。对应原3.8.4手动工具闭环，后续4.3多轮继续。

## 新增API与调用关系

ad_report_tool.invoke(args)为实际工具对象方法：Pydantic校验参数后执行get_ad_report，返回报表字典。ad_tool_model.ainvoke(messages)为模型请求。ToolMessage(content,tool_call_id)表示工具执行结果，id必须匹配原调用id。messages.append(first)保存原模型消息及工具调用请求，再追加每个ToolMessage，最后model.ainvoke(messages)总结。

本块固定一次工具批次、最多4个调用，最多两次模型请求；第二次基础model没有绑定工具，仅总结。缺编号时第一次直接询问，一次模型请求结束。D06多轮及总轮次限制下一块，当前不会无限回边。

## llm_service.py新增导入

```python
import json  # 把工具结果字典转为消息中的JSON文本。
from langchain_core.messages import ToolMessage  # 工具结果消息类型。
```

## llm_service.py末尾新增完整函数

```python
async def run_ad_tool(input_text: str) -> dict:
    messages = [
        {
            "role": "system",
            "content": (
                "你是广告报表助手，报表来自合成样例。"
                "查询报表时使用工具，缺少广告编号先询问。"
                "根据工具实际结果回答；工具失败时说明失败。"
            ),
        },
        {"role": "user", "content": input_text},
    ]

    first = await ad_tool_model.ainvoke(messages)  # 第一次：模型选择工具。
    if first.invalid_tool_calls:
        raise OutputParserException("模型生成的工具参数无法解析")
    if not first.tool_calls:  # 如缺编号，直接返回模型的询问。
        return {"answer": first.content, "tool_results": []}
    if len(first.tool_calls) > 4:  # 限制本批次的调用数量。
        raise OutputParserException("本次工具调用数量超过上限4次")
    for call in first.tool_calls:
        if not call.get("id"):
            raise OutputParserException("工具调用缺少匹配编号")

    messages.append(first)  # 必须保留模型原始的工具调用消息。
    tool_results = []  # 保存本次执行记录，供浏览器核对。

    for call in first.tool_calls:
        if call["name"] != ad_report_tool.name:
            result = {"error": "unknown_tool", "message": "请求的工具未开放"}
        else:
            try:
                # 实际校验参数并执行ad_tools.py中的查询函数。
                result = ad_report_tool.invoke(call["args"])
            except ValidationError:
                result = {"error": "invalid_arguments", "message": "广告编号须为非空字符串"}
            except ValueError:
                result = {"error": "report_not_found", "message": "未找到该广告活动的样例报表"}

        messages.append(ToolMessage(
            content=json.dumps(result, ensure_ascii=False),  # 字典转JSON文本。
            tool_call_id=call["id"],  # 与模型提出请求时的id一致。
            name=call["name"],  # 记录本条结果所属的工具。
        ))
        tool_results.append({
            "name": call["name"],
            "args": call["args"],
            "tool_call_id": call["id"],
            "result": result,
        })

    final = await model.ainvoke(messages)  # 第二次：基础模型根据工具结果作答。
    return {"answer": final.content, "tool_results": tool_results}
```

ValidationError/model/ad_tool_model/ad_report_tool/OutputParserException复用已有定义与导入。同步invoke只执行本地固定查询，后续IO工具使用异步客户端。返回错误作为工具结果让模型知晓，仍需保留调用与结果配对；未知工具只在开放清单内分派，模型给的工具名不作为任意Python执行入口。

## main.py新增导入与完整接口

```python
from llm_service import run_ad_tool  # 导入新增的完整工具闭环函数。
```

```python
@app.post("/ads/chat")
async def ad_chat(body: RequirementInput):
    try:
        return await run_ad_tool(body.input)  # 模型选工具→后端执行→模型总结。
    except APITimeoutError as error:
        raise HTTPException(status_code=504, detail="模型请求超时") from error
    except OutputParserException as error:
        raise HTTPException(status_code=502, detail="模型工具请求解析失败") from error
    except OpenAIError as error:
        raise HTTPException(status_code=502, detail="模型服务调用失败") from error
```

旧接口继续保留。调用图：浏览器POST /ads/chat→main.ad_chat→llm_service.run_ad_tool→第一次模型→ad_report_tool.invoke→get_ad_report→ToolMessage→第二次模型→answer/tool_results→浏览器。模块加载只定义配置与函数；请求到来时执行上述模型及查询。

## 浏览器验收与答案

8000/docs的POST /ads/chat提交{"input":"查询AD-DEMO-001的广告花费和归因销售额。"}。预期tool_results有花费100、销售250、synthetic_demo，answer依据这些值并标合成数据；实际供应商结果待学生提交。改为AD-DEMO-999，若模型调用该编号，应见report_not_found并说明失败。缺编号允许先询问且tool_results为空。

必背：模型产生调用请求，后端用工具对象校验执行，再用ToolMessage携带匹配的tool_call_id回传；保留原AIMessage与结果消息一起交给模型，最终回答才能基于执行结果。工具结果成功与最终生成质量分别核对。

D06进行中，剩余实际闭环结果、多轮与上限、计算工具、失败/重复调用和库存迁移，独立完整通过1/32，D05缺口保留。

教师验证：使用真实LangChain工具/Pydantic/ToolMessage与模型固定返回，成功报表、未知活动、非法参数、未知工具、消息协议配对、缺编号直接询问、批次上限及缺id拒绝均通过；FastAPI接口200/422/502通过。固定答复用于控制流程检查，供应商调用0次，最终模型内容质量待学生实测。
