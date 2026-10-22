# D06：计算工具与多轮工具调用。日期：10/22

日历目标D05，实际D06。原课4.3.2的有界工具循环，沿用POST /ads/chat→main.py→llm_service.run_ad_tool。学生业务源码由学生按对话修改；教师仅维护讲义和进度。

必备：模型返回工具名称/参数，后端根据名称选择已注册工具并执行，再用ToolMessage回填结果；模型可以在下一轮继续申请工具。无tool_calls返回最终答复，达到轮次上限返回limit_reached。max_retries控制失败重试，循环次数控制正常任务推进中的模型调用次数，两项独立。

ROAS=归因销售额/广告花费；当前合成样例250/100=2.5。花费0时返回不可计算；ROAS代表广告投入对应的归因销售额，利润还涉及成本费用等。calculate_roas只接收campaign_id，在后端获取报表并计算，避免让模型提供计算金额。当前固定合成报表可重复读取；后续真实数据需固定报表日期和快照。

改动：ad_tools.py末尾追加计算工具；llm_service.py原ad_tools导入和bind_tools声明替换，原run_ad_tool整函数替换。main.py沿用。tools_by_name是允许执行的工具字典，.get读取工具对象。for range(4)最多4次模型请求，每次最多4个工具调用，总执行上限16次。最后一轮回填后达到上限，保留实际结果，明确报告未完成；不给无依据成功文案。

## ad_tools.py末尾追加

```python
@tool("calculate_roas", args_schema=AdReportInput)
def calculate_roas_tool(campaign_id: str) -> dict:
    """根据广告活动编号读取合成样例报表，计算ROAS；花费为0时说明无法计算。"""
    report = get_ad_report(campaign_id)  # 后端读取报表，金额来自已有数据。
    spend = report["spend"]  # 读取广告花费。
    return {
        "data_source": report["data_source"],  # 保留合成数据标记。
        "campaign_id": campaign_id,  # 返回此次计算的广告编号。
        "spend": spend,  # 返回计算依据。
        "attributed_sales": report["attributed_sales"],  # 返回归因销售额。
        "roas": round(report["attributed_sales"] / spend, 4) if spend > 0 else None,
        "message": "计算完成" if spend > 0 else "广告花费为0，ROAS无法计算",
    }
```

## llm_service.py替换原工具导入/绑定两处

```python
from ad_tools import ad_report_tool, calculate_roas_tool  # 导入两个工具对象。
ad_tool_model = model.bind_tools([ad_report_tool, calculate_roas_tool])  # 提供两种工具说明。
```

保留已有json、ToolMessage、ValidationError、OutputParserException导入。

## llm_service.py替换整个run_ad_tool

```python
async def run_ad_tool(input_text: str) -> dict:
    tools_by_name = {  # 后端允许执行的工具；工具名称对应实际对象。
        ad_report_tool.name: ad_report_tool,
        calculate_roas_tool.name: calculate_roas_tool,
    }
    messages = [
        {"role": "system", "content": (
            "你是广告报表助手，数据来自合成样例，答复必须注明。"
            "查询报表使用get_ad_report，计算ROAS使用calculate_roas。"
            "缺少广告编号先询问；根据成功的工具结果回答。"
            "工具失败时说明失败，避免相同参数重复调用同一工具。"
            "ROAS不能直接表示利润，也不足以单独决定调整预算。"
        )},
        {"role": "user", "content": input_text},  # 当前用户问题。
    ]
    tool_results = []  # 累积本次请求实际执行的工具结果。

    for model_turn in range(4):  # 依次为0、1、2、3，最多请求模型4次。
        response = await ad_tool_model.ainvoke(messages)  # 每次都携带已积累的消息。
        if response.invalid_tool_calls:
            raise OutputParserException("模型生成的工具参数无法解析")
        if not response.tool_calls:  # 模型本轮直接给出答复，结束本函数。
            return {"status": "completed", "answer": response.content,
                    "tool_results": tool_results}
        if len(response.tool_calls) > 4:
            raise OutputParserException("单轮工具调用数量超过上限4次")
        for call in response.tool_calls:  # 执行前检查每个调用的配对编号。
            if not call.get("id"):
                raise OutputParserException("工具调用缺少匹配编号")

        messages.append(response)  # 保存模型原消息，包含本轮tool_calls。
        for call in response.tool_calls:
            selected_tool = tools_by_name.get(call["name"])  # 按名字取出允许的工具。
            if selected_tool is None:
                result = {"error": "unknown_tool", "message": "请求的工具未开放"}
            else:
                try:
                    result = selected_tool.invoke(call["args"])  # 校验参数并执行Python函数。
                except ValidationError:
                    result = {"error": "invalid_arguments", "message": "广告编号须为非空字符串"}
                except ValueError:
                    result = {"error": "report_not_found", "message": "未找到该广告活动的样例报表"}

            messages.append(ToolMessage(  # 将此次执行结果放入下一轮模型消息。
                content=json.dumps(result, ensure_ascii=False),  # 字典转JSON文本。
                tool_call_id=call["id"],  # 与模型原调用编号配对。
                name=call["name"],  # 标明结果属于哪个工具。
            ))
            tool_results.append({  # 同时保留给浏览器检查的执行记录。
                "name": call["name"], "args": call["args"],
                "tool_call_id": call["id"], "result": result,
            })
        # 本轮工具全部执行完，for自动进入下一轮模型请求。

    return {  # 4次模型请求用完，明确返回处理上限和已经完成的结果。
        "status": "limit_reached",
        "answer": "已达到本次4次模型请求上限，请查看已取得的工具结果。",
        "tool_results": tool_results,
    }
```

浏览器8000/docs→POST /ads/chat，输入：先查询AD-DEMO-001的花费和归因销售额，再调用计算工具计算ROAS，并解释数值。检查calculate_roas结果2.5、样例提示、status。模型有可能直接选计算工具，该工具内部仍实际读取报表；以实际调用轨迹为证据。程序级重复调用去重和库存迁移后续讲解。

必背答案：多轮工具调用时，后端将模型的工具请求和工具实际结果一起加入消息，再次请求模型；模型无工具请求时结束，程序同时设置最大轮次。max_retries限制失败重试次数，循环上限限制任务推进轮次。

来源：https://docs.langchain.com/oss/python/langchain/models#tool-calling 。原课chapter-04-LangChain进阶/course.md 4.3.2。业务计算按本例归因销售额/花费定义；真实平台还需核对归因窗口和数据口径。
