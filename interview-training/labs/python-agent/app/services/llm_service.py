import os  # 读取进程环境变量。
from pathlib import Path  # 定位项目根目录下的.env。
from dotenv import load_dotenv  # 从本地.env加载配置。
from langchain_openai import ChatOpenAI  # LangChain的模型调用组件。
from langchain_core.exceptions import OutputParserException  # 表示结果解析失败。
from app.schemas.requirements import RequirementResult  # 模型输出的校验规则。
from app.prompts.requirements import build_messages  # 复用已有的消息组装函数。
import json  # 把字典转成JSON文本。
from langchain_core.messages import ToolMessage  # 工具结果消息。
from pydantic import ValidationError
import asyncio  # Python自带的异步工具。
# 读取python-agent根目录的.env；进程已有的环境变量优先。
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

if os.environ.get("OPENAI_MODEL") != "deepseek-v4-pro-0813":
    raise RuntimeError("本课程只允许deepseek-v4-pro-0813，请检查OPENAI_MODEL并重启服务")




model = ChatOpenAI(  # 创建模型调用对象；此时尚未发送请求。
    model=os.environ["OPENAI_MODEL"],  # 从环境变量读取模型名。
    api_key=os.environ["OPENAI_API_KEY"],  # 后端读取密钥。
    base_url=os.environ["OPENAI_BASE_URL"],  # 使用原项目的接口基础地址。
    temperature=0,  # 降低采样随机性，实际结果仍须检查。
    timeout=30,  # HTTP超时配置，单位为秒。
    max_retries=0,  # 当前失败直接返回，方便定位第一次错误。
    use_responses_api=False,  # 显式使用Chat Completions接口。
)

structured_model = model.with_structured_output(
    RequirementResult,
    method="function_calling",  # 通过工具调用协议声明输出结构。
)

async def extract_requirement(input_text: str) -> RequirementResult:
    # 调用app/prompts/requirements.py，与预览接口共用同一套消息。
    messages = build_messages(input_text)

    # 把消息发送给结构化模型，等待返回结果。
    result = await structured_model.ainvoke(messages)

    # 保留已有保护：模型结果必须是RequirementResult对象。
    if not isinstance(result, RequirementResult):
        raise OutputParserException("模型未返回有效结构化结果")

    # 返回通过字段校验的结果。
    return result


from app.tools.ad_tools import (
    ad_report_tool,
    calculate_roas_tool,
    inventory_tool,  # 新增：导入库存工具对象。
)

ad_tool_model = model.bind_tools([
    ad_report_tool,
    calculate_roas_tool,
    inventory_tool,  # 新增：把库存工具说明提供给模型。
])


async def request_ad_tool(input_text: str) -> dict:
    # 这里才真正发送模型请求，等待模型选择工具或直接回答。
    response = await ad_tool_model.ainvoke([
        {
            "role": "system",
            "content": (
                "你是广告报表助手。查询报表时使用get_ad_report工具。"
                "广告编号缺失时先询问编号；数据来源为合成样例。"
                "工具结果返回后才能据此描述花费或销售额。"
            ),
        },
        {
            "role": "user",
            "content": input_text,
        },
    ])

    # LangChain无法解析工具参数时，返回已有的解析异常。
    if response.invalid_tool_calls:
        raise OutputParserException("模型生成的工具参数无法解析")

    return {
        "content": response.content,        # 模型文字内容，可能为空。
        "tool_calls": response.tool_calls,  # 模型提出的工具调用请求。
    }


async def run_ad_tool(
    input_text: str,
    history: list[dict] | None = None,
) -> dict:
    tools_by_name = {
        ad_report_tool.name: ad_report_tool,
        calculate_roas_tool.name: calculate_roas_tool,
        inventory_tool.name: inventory_tool,  # 新增：允许后端执行库存工具。
    }

    messages = [
        {
            "role": "system",
            "content": (
                "你是电商运营助手，数据来自合成样例，答复必须注明。"
                "查询广告使用get_ad_report，计算ROAS使用calculate_roas。"
                "查询库存使用get_inventory，根据返回的is_low_stock解释库存情况。"
                "广告编号或商品编号缺失时先询问，根据成功工具结果回答。"
                "库存不足时提供提醒建议，实际通知的发送需要另行接入通知工具。"
                "工具失败时说明失败，避免相同参数重复调用同一工具。"
                "投放是否有效需要结合目标ROAS、毛利和其他费用判断。"
            ),
        },
    ]

    messages.extend(history or [])  # 加入以前已完成的多条消息。
    messages.append(
        {"role": "user", "content": input_text}
    )  # 最后加入本次输入。

    tool_results = []  # 保存本次请求的工具记录。
    result_cache = {}  # 新增：保存本次请求内的成功结果。

    for model_turn in range(4):  # 保留：最多请求模型4次。
        response = await ad_tool_model.ainvoke(messages)

        if response.invalid_tool_calls:
            raise OutputParserException("模型生成的工具参数无法解析")

        if not response.tool_calls:
            return {
                "status": "completed",
                "answer": response.content,
                "tool_results": tool_results,
            }

        if len(response.tool_calls) > 4:
            raise OutputParserException("单轮工具调用数量超过上限4次")

        for call in response.tool_calls:
            if not call.get("id"):
                raise OutputParserException("工具调用缺少匹配编号")

        messages.append(response)  # 保存模型原消息及工具请求。

        for call in response.tool_calls:
            selected_tool = tools_by_name.get(call["name"])

            # 新增：用工具名称和参数识别是否为相同操作。
            cache_key = json.dumps(
                {"name": call["name"], "args": call["args"]},
                sort_keys=True,
                ensure_ascii=False,
            )

            # 新增：缓存中已有成功结果时，标记为复用。
            reused = cache_key in result_cache

            if reused:
                result = result_cache[cache_key]  # 新增：读取已有结果。

            elif selected_tool is None:
                result = {
                    "error": "unknown_tool",
                    "message": "请求的工具未开放",
                }

            else:
                try:
                    # 首次执行时，仍由工具校验参数并执行函数。
                    result = await asyncio.to_thread(
                        selected_tool.invoke,  # 交给线程执行的函数。
                        call["args"],  # 传给invoke的工具参数。
                    )
                except ValidationError:
                    result = {
                    "error": "invalid_arguments",
                    "message": "工具参数不符合要求，请检查字段及类型",
                }

                except ValueError:
                    result = {
                    "error": "data_not_found",
                    "message": "未找到该编号对应的样例数据",
                }

            # 新增：只保存成功结果，失败结果继续允许再次尝试。
            if "error" not in result:
                result_cache[cache_key] = result

            messages.append(
                ToolMessage(
                    content=json.dumps(result, ensure_ascii=False),
                    tool_call_id=call["id"],  # 始终对应当前这次工具请求。
                    name=call["name"],
                )
            )

            tool_results.append({
                "name": call["name"],
                "args": call["args"],
                "tool_call_id": call["id"],
                "result": result,
                "reused": reused,  # 新增：浏览器可查看是否复用。
            })

    return {
        "status": "limit_reached",
        "answer": "已达到本次4次模型请求上限，请查看已取得的工具结果。",
        "tool_results": tool_results,
    }
