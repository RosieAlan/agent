import re  # Python自带的正则工具，用来识别广告编号。

from langgraph.graph import StateGraph, START, END

from app.services.ad_intent_service import classify_ad_intent
from app.graphs.ad_report_graph import (
    AdState,
    ad_graph,
    load_report,
)
import logging  # Python自带日志工具。

from openai import (
    APIConnectionError,  # 模型服务连接失败。
    APITimeoutError,     # 模型请求超时。
    RateLimitError,      # 模型服务限流。
    InternalServerError,  # 模型供应商服务端错误。
)
from langchain_core.exceptions import OutputParserException

# class AdChatState(AdState):
#     # 继承原AdState的user_id、report、roas等字段，再增加三个字段。
#     input: str
#     intent: str
#     reason: str
class AdChatState(AdState):
    input: str
    intent: str
    reason: str
    classification_source: str  # 新增：记录本次分类结果来自哪里。

def fallback_classification(input_text: str) -> dict:
    # 去除首尾空白及常见句末标点，便于匹配。
    text = input_text.strip().rstrip("。！？!?，, ")

    if text.lower() in {"你好", "您好", "谢谢", "hi", "hello"}:
        intent = "chat"
        reason = "规则识别到独立的问候或感谢。"

    elif re.fullmatch(
        r"(查询|查看)\s*(AD-[A-Z0-9]+(?:-[A-Z0-9]+)*)?"
        r"\s*(的)?\s*(花费|报表|分析报告)",
        text,
        flags=re.IGNORECASE,
    ):
        intent = "query"
        reason = "规则识别到查询已有广告数据的请求。"

    elif re.fullmatch(
        r"(分析|评估)\s*(AD-[A-Z0-9]+(?:-[A-Z0-9]+)*)?"
        r"\s*(的)?\s*(投放效果|广告效果|表现)",
        text,
        flags=re.IGNORECASE,
    ):
        intent = "analyze"
        reason = "规则识别到广告效果分析请求。"

    else:
        intent = "clarify"
        reason = "备用规则暂时无法明确判断用户要执行的任务。"

    return {
        "intent": intent,
        "reason": reason,
        "classification_source": "rule_fallback",
    }

async def classifier(state: AdChatState) -> dict:
    try:
        # 正常路径：调用已有模型分类服务。
        result = await classify_ad_intent(state["input"])

        decision = {
            "intent": result.intent,
            "reason": result.reason,
            "classification_source": "model",
        }

    except (
        APIConnectionError,
        APITimeoutError,
        RateLimitError,
        InternalServerError,
        OutputParserException,
    ) as error:
        # 只记录错误类型，避免把凭据和完整请求写进日志。
        logging.getLogger(__name__).warning(
            "ad_intent_fallback error_type=%s",
            type(error).__name__,
        )

        # 指定错误发生后，用本地规则继续判断。
        decision = fallback_classification(state["input"])

    # 沿用已有广告编号提取逻辑。
    campaign_ids = re.findall(
        r"AD-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*",
        state["input"],
        flags=re.IGNORECASE,
    )

    campaign_ids = list(dict.fromkeys(
        item.upper() for item in campaign_ids
    ))

    return {
        **decision,  # 展开分类结果，放入本次State更新。
        "campaign_id": (
            campaign_ids[0] if len(campaign_ids) == 1 else ""
        ),
    }


def route_by_intent(state: AdChatState) -> str:
    # 问候直接回复；分类不明确时进入澄清。
    if state["intent"] in {"chat", "clarify"}:
        return state["intent"]

    # 查询或分析缺少明确编号时，同样进入澄清。
    if not state["campaign_id"]:
        return "clarify"

    return state["intent"]


def ask_campaign_id(state: AdChatState) -> dict:
    if state["intent"] == "clarify":
        return {
            "summary": (
                "当前暂时无法判断你的具体任务。"
                "请明确说明要查询广告报表，还是分析投放效果，"
                "并提供一个广告编号。"
            ),
        }

    return {
        "summary": (
            "请提供一个广告编号，例如AD-DEMO-001。"
            "当前每次处理一个广告活动。"
        ),
    }


def query_report(state: AdChatState) -> dict:
    # 复用查询节点，继续按用户、店铺和广告编号检查可访问报表。
    updates = load_report(state)
    report = updates["report"]
    return {
        "report": report,
        "summary": (
            f"广告{state['campaign_id']}，"
            f"花费：{report['spend']}，"
            f"归因销售额：{report['attributed_sales']}。"
            f"数据来源：{report['data_source']}。"
        ),
    }


def reply_chat(state: AdChatState) -> dict:
    # 当前用固定问候介绍支持范围，减少额外模型请求。
    return {
        "summary": "你好，我可以帮你查询广告报表或分析广告效果。"
    }


ad_chat_graph = (
    StateGraph(AdChatState)

    .add_node("classifier", classifier)
    .add_node("query", query_report)

    # 直接复用已经compile的广告分析图，作为当前图的一个节点。
    .add_node("analyze", ad_graph)

    .add_node("chat", reply_chat)
    .add_node("clarify", ask_campaign_id)

    .add_edge(START, "classifier")  # 收到请求后先分类。

    .add_conditional_edges(
        "classifier",     # 分类完成后开始选路。
        route_by_intent,  # 读取State并返回路径名称。
        {
            "query": "query",
            "analyze": "analyze",
            "chat": "chat",
            "clarify": "clarify",
        },
    )

    .add_edge("query", END)
    .add_edge("analyze", END)
    .add_edge("chat", END)
    .add_edge("clarify", END)

    .compile()
)
