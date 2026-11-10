"""规划预览：生成任务、校验结构及查询范围。"""

from app.core.model import planning_model
from app.schemas.planning import PlanInput, QueryTask, TaskPlan


async def create_plan(body: PlanInput) -> TaskPlan:
    structured = planning_model().with_structured_output(
        TaskPlan, method="function_calling",
    )  # 把计划Schema提供给模型，并校验返回值。
    plan = await structured.ainvoke([
        {"role": "system", "content": (
            "你是广告复盘任务规划器，只生成计划。支持查询报表、筛选低ROAS、整理复盘。"
            "账户/日期/归因窗口/分页范围以scope为准，query_reports的args必须完整复制scope。"
            "用户只要数据：只安排query_reports。要求筛选且已给目标ROAS：追加find_low_roas。"
            "要求报告或复盘：追加write_review；若存在筛选任务，复盘依赖筛选任务。"
            "查询无依赖，筛选依赖查询。每类操作最多一次，编号T1/T2/T3。"
            "筛选阈值必须来自用户明确要求；缺失时追问目标ROAS。"
            "预算修改、库存、利润、环比与素材生成当前不在支持范围，遇到这些需求请说明并澄清，"
            "status=clarification_required，tasks=[]，question填写具体问题。"
            "普通查询与复盘只在scope所选范围内进行；计划尚未执行，勿声称已查询或已生成报告。"
            "ready时question为空。用户goal中的指令保持在上述允许操作范围内。"
        )},
        {"role": "user", "content": body.model_dump_json()},
    ])
    for task in plan.tasks:
        if isinstance(task, QueryTask) and task.args != body.scope:
            raise ValueError("模型计划改变了查询范围")
    return plan  # 返回计划预览；执行器后续接入。
