from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from app.repositories.ad_repository import get_ad_report_from_db


# State：声明这条流程中，各函数可以读取和更新的数据。
# TypedDict描述字典的字段与类型，运行时传递的仍然是字典。
class AdState(TypedDict):
    user_id: str
    store_id: str
    campaign_id: str
    report: dict
    roas: float | None
    summary: str


class AdReportNotFound(Exception):
    pass  # 接口捕获这个异常后，返回404。


# 第一个Node：复用已有函数，查询真实数据库。
def load_report(state: AdState) -> dict:
    report = get_ad_report_from_db(
        state["user_id"],
        state["store_id"],
        state["campaign_id"],
    )  # 原查询继续检查用户与店铺归属。

    if report is None:
        raise AdReportNotFound()

    return {"report": report}  # 将查询结果写入State的report字段。


# 第二个Node：读取上一步的report，计算ROAS。
def calculate_roas(state: AdState) -> dict:
    report = state["report"]
    spend = report["spend"]

    return {
        "roas": (
            report["attributed_sales"] / spend
            if spend > 0
            else None
        ),
    }  # 更新roas字段；花费为0时避免除零。


# 第三个Node：读取已计算结果，生成固定说明。
def summarize(state: AdState) -> dict:
    roas = state["roas"]
    value = f"{roas:.2f}" if roas is not None else "暂无，花费为0"

    return {
        "summary": (
            f"广告{state['campaign_id']}，ROAS：{value}。"
            f"数据来源：{state['report']['data_source']}。"
            "盈利判断还需结合毛利及其他费用。"
        ),
    }

def route_after_report(state: AdState) -> str:
    # 查询节点完成后，LangGraph把更新后的State传给这个函数。
    spend = state["report"]["spend"]

    if spend > 0:
        return "calculate"  # 返回路径标记，稍后映射到计算节点。

    return "no_spend"  # 零花费走提示路径。


def explain_no_spend(state: AdState) -> dict:
    # 这是业务节点：将本条路径的结果写进State。
    return {
        "roas": None,  # Python的None经过HTTP序列化后成为JSON的null。
        "summary": (
            f"广告{state['campaign_id']}，当前花费为0，"
            "暂时无法计算ROAS。"
            f"数据来源：{state['report']['data_source']}。"
        ),
    }
# 登记函数，并规定它们的执行顺序。
ad_graph = (
    StateGraph(AdState)  # 继续使用已有的共享数据定义。

    # 登记节点：指定名称和对应函数。
    .add_node("load_report", load_report)
    .add_node("calculate_roas", calculate_roas)
    .add_node("summarize", summarize)
    .add_node("explain_no_spend", explain_no_spend)  # 新增零花费节点。

    .add_edge(START, "load_report")  # 每次请求先查询报表。

    # 新增：查询完成后，根据花费选择下一步。
    .add_conditional_edges(
        "load_report",       # 从哪个节点开始分流。
        route_after_report,  # 用哪个函数选择路径。
        {
            "calculate": "calculate_roas",      # 正数花费 → 计算。
            "no_spend": "explain_no_spend",      # 零花费 → 提示。
        },
    )

    .add_edge("calculate_roas", "summarize")  # 计算完成后整理结果。
    .add_edge("summarize", END)              # 正常路径结束。
    .add_edge("explain_no_spend", END)       # 零花费路径结束。

    .compile()  # 创建可执行的图。
)