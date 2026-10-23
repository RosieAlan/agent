# D06：重复调用防护。日期：10/23

沿用/ads/chat→run_ad_tool。原课4.3.2工具循环，面试补充：本次请求内相同工具名+相同参数复用成功结果；失败结果保留再次尝试，四轮模型上限继续生效。call id用于消息配对，缓存键用于识别相同操作，两项分开。只适用于当前只读合成报表；跨请求、写操作幂等与实时刷新另按后续课程设计。

新增result_cache放在for循环外/函数内；sort_keys=True让参数键顺序固定。缓存命中仍须给当前call id回填ToolMessage，每次请求仍保留工具记录并加reused。所有业务代码由学生修改。

```python
async def run_ad_tool(input_text: str) -> dict:
    tools_by_name = {  # 名称对应后端实际允许执行的工具。
        ad_report_tool.name: ad_report_tool,
        calculate_roas_tool.name: calculate_roas_tool,
    }

    messages = [
        {
            "role": "system",
            "content": (
                "你是广告报表助手，数据来自合成样例，答复必须注明。"
                "查询报表使用get_ad_report，计算ROAS使用calculate_roas。"
                "缺少广告编号先询问，根据成功的工具结果回答。"
                "工具失败时说明失败，避免相同参数重复调用同一工具。"
                "投放是否有效需要结合目标ROAS、毛利和其他费用判断。"
            ),
        },
        {
            "role": "user",
            "content": input_text,  # 浏览器提交的问题。
        },
    ]

    tool_results = []  # 保存本次请求中所有工具执行记录。
    result_cache = {}  # 新增：只在本次HTTP请求内保存成功结果。

    for model_turn in range(4):  # 最多请求模型4次。
        response = await ad_tool_model.ainvoke(messages)

        if response.invalid_tool_calls:
            raise OutputParserException("模型生成的工具参数无法解析")

        if not response.tool_calls:
            # 本轮模型给出答复，结束整个函数。
            return {
                "status": "completed",
                "answer": response.content,
                "tool_results": tool_results,
            }

        if len(response.tool_calls) > 4:
            raise OutputParserException("单轮工具调用数量超过上限4次")

        for call in response.tool_calls:
            if not call.get("id"):  # 工具结果需要通过id对应原请求。
                raise OutputParserException("工具调用缺少匹配编号")

        messages.append(response)  # 保存模型消息及其中的工具请求。

        for call in response.tool_calls:
            # 按模型返回的名称，找到后端已开放的工具。
            selected_tool = tools_by_name.get(call["name"])

            cache_key = json.dumps(  # 新增：工具名和参数共同决定是否重复。
                {"name": call["name"], "args": call["args"]},
                sort_keys=True, ensure_ascii=False,  # 固定字典键顺序。
            )
            reused = cache_key in result_cache  # 新增：这次是否复用成功结果。

            if reused:
                result = result_cache[cache_key]  # 新增：直接取出之前的结果。
            elif selected_tool is None:
                result = {
                    "error": "unknown_tool",
                    "message": "请求的工具未开放",
                }
            else:
                try:
                    # 工具对象校验参数，再执行你定义的Python函数。
                    result = selected_tool.invoke(call["args"])

                except ValidationError:
                    result = {
                        "error": "invalid_arguments",
                        "message": "广告编号须为非空字符串",
                    }

                except ValueError:
                    result = {
                        "error": "report_not_found",
                        "message": "未找到该广告活动的样例报表",
                    }

            if "error" not in result:  # 新增：成功结果才进入本次请求的缓存。
                result_cache[cache_key] = result

            messages.append(
                ToolMessage(
                    content=json.dumps(result, ensure_ascii=False),
                    tool_call_id=call["id"],  # 与原工具请求配对。
                    name=call["name"],
                )
            )

            tool_results.append({  # 同时保留给浏览器查看的执行记录。
                "name": call["name"],
                "args": call["args"],
                "tool_call_id": call["id"],
                "result": result,
                "reused": reused,  # 新增：浏览器可查看是否复用。
            })

        # 工具执行完毕，自动进入下一轮。
        # 下一轮模型会看到已加入messages的工具结果。

    return {  # 四次模型请求用完，保留已有结果并明确报告上限。
        "status": "limit_reached",
        "answer": "已达到本次4次模型请求上限，请查看已取得的工具结果。",
        "tool_results": tool_results,
    }
```

本地真实工具+固定模型测试通过：重复成功实际执行一次、每次id正确配对、新HTTP调用不复用、失败不缓存、四轮上限有效。供应商调用0次。学生浏览器证据待交；模型未重复请求时无法据此验证缓存命中。

必背：相同工具名和参数在本次请求内复用成功结果，每个工具请求仍用自己的call id回填；循环上限独立约束模型请求轮次。只读缓存与跨请求写操作幂等分别处理。
