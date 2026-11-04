# D09-01：将广告查询计算迁移为LangGraph固定流程。日期：11/04

用户明确授权提前D09，要求简明概念在实战补齐。D08只读展示/动作路径证据保留；表单/确认/交互状态/流式进度/其余协议/三层策略逐项结合D09/D10/D12补讲验收，D08未据此标全通过。原课8.1–8.3固定工作流图化；沿用D07数据与权限过滤，先在小业务完成3节点，再覆盖原5阶段迁移及分支/回边。LangGraph负责状态与控制流，节点可执行数据库、普通计算或模型；当前0模型。本机langgraph缺失，兼容性dry-run后安装1.2.19，现有langchain-core1.6.13保持。

新增app/graphs/__init__.py空文件、app/graphs/ad_report_graph.py：
```python
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from app.repositories.ad_repository import get_ad_report_from_db


class AdState(TypedDict):
    user_id: str
    store_id: str
    campaign_id: str
    report: dict
    roas: float | None
    summary: str


class AdReportNotFound(Exception):
    pass  # HTTP接口捕获后返回404。


def load_report(state: AdState) -> dict:
    report = get_ad_report_from_db(
        state["user_id"], state["store_id"], state["campaign_id"],
    )  # 复用D07查询，继续检查用户与店铺归属。
    if report is None:
        raise AdReportNotFound()
    return {"report": report}  # 只更新本步骤产出的字段。


def calculate_roas(state: AdState) -> dict:
    report = state["report"]  # 读取上一个节点写入的数据。
    spend = report["spend"]
    return {
        "roas": report["attributed_sales"] / spend if spend > 0 else None,
    }  # 花费为0时返回None，避免除零。


def summarize(state: AdState) -> dict:
    roas = state["roas"]
    value = f"{roas:.2f}" if roas is not None else "暂无，花费为0"
    return {
        "summary": f"广告{state['campaign_id']}，ROAS：{value}。"
        f"数据来源：{state['report']['data_source']}。"
        "盈利判断还需结合毛利及其他费用。",
    }


ad_graph = (
    StateGraph(AdState)  # 定义整张图可以读写哪些字段。
    .add_node("load_report", load_report)  # 登记查询函数，暂未执行。
    .add_node("calculate_roas", calculate_roas)
    .add_node("summarize", summarize)
    .add_edge(START, "load_report")  # 图启动后先查询。
    .add_edge("load_report", "calculate_roas")  # 查询完成再计算。
    .add_edge("calculate_roas", "summarize")  # 计算完成再整理结果。
    .add_edge("summarize", END)  # 整理完成后结束。
    .compile()  # 检查图结构并创建可执行对象。
)
```

在已有app/api/ads.py末尾追加，已有路由已在main登记：
```python
# 新增在app/api/ads.py末尾；复用本文件已有router和数据库异常导入。
from app.graphs.ad_report_graph import ad_graph, AdReportNotFound


@router.get("/ads/graph/{campaign_id}")
def ad_graph_report(campaign_id: str):
    try:
        result = ad_graph.invoke({
            "user_id": "user-001",  # 当前本地演练身份，继续由后端指定。
            "store_id": "store-A",
            "campaign_id": campaign_id,
            "report": {},
            "roas": None,
            "summary": "",
        })  # 本次请求到达时，才按边的顺序执行节点。
        return {
            "campaign_id": result["campaign_id"],
            "data_source": result["report"]["data_source"],
            "spend": result["report"]["spend"],
            "attributed_sales": result["report"]["attributed_sales"],
            "roas": result["roas"],
            "summary": result["summary"],
        }
    except AdReportNotFound as error:
        raise HTTPException(404, "未找到可访问的广告报表") from error
    except (OperationalError, PoolTimeoutError) as error:
        raise HTTPException(503, "报表数据库暂时不可用") from error
    except SQLAlchemyError as error:
        raise HTTPException(500, "报表查询失败") from error
```

必背：State保存步骤间共享的数据，Node是执行工作的函数，Edge决定下一个函数。TypedDict描述字典键及类型，实际变量仍为字典；当前节点更新的字段默认覆盖，其他字段保留。add_node登记函数，add_edge指定顺序，compile创建可执行图，invoke执行本次请求。节点返回部分更新，避免整个state复制。编译时不查库，收到HTTP请求才invoke。sync FastAPI接口在线程池执行，数据库Session仍由原repository归还连接。

浏览器GET http://127.0.0.1:8000/ads/graph/AD-DEMO-001应100/250/2.5及来源说明，未知编号404，数据库故障503/SQL错误500。当前图无checkpointer，每次请求重新执行；持久化及暂停恢复D10。图中普通串行边当前固定顺序，路由与ReAct回边后续升级；原需求5阶段迁移仍在D09去向保留。学生写业务，教师候选验证及文档维护。

