from langchain_core.tools import tool  # 将函数包装成LangChain工具。
from pydantic import BaseModel, ConfigDict, Field  # 已学过的参数校验。
from app.repositories.ad_repository import get_ad_report_from_db  # 导入数据库查询函数。
from app.repositories.inventory_repository import get_inventory_from_db
# 复用已有的库存数据库查询函数。
def get_ad_report(campaign_id: str) -> dict:
    report = get_ad_report_from_db(
        user_id="user-001",  # 当前本地演示用户。
        store_id="store-A",  # 当前本地演示店铺。
        campaign_id=campaign_id,  # 用户或模型提供的广告编号。
    )

    if report is None:
        raise ValueError("未找到可访问的广告报表")

    return report  # 将数据库结果交给原来的调用方。

class AdReportInput(BaseModel):
    # 新增：规定工具接收的参数。
    model_config = ConfigDict(
        strict=True,
        str_strip_whitespace=True,
    )

    campaign_id: str = Field(
        min_length=1,
        description="广告活动编号，例如AD-DEMO-001",
    )


@tool("get_ad_report", args_schema=AdReportInput)
def ad_report_tool(campaign_id: str) -> dict:
    """查询指定广告活动的合成样例报表，返回花费、归因销售额、点击和展示。"""
    # 真正执行工具时，仍调用上面的普通查询函数。
    return get_ad_report(campaign_id)


@tool("calculate_roas", args_schema=AdReportInput)
def calculate_roas_tool(campaign_id: str) -> dict:
    """读取指定广告的合成样例报表并计算ROAS，花费为0时说明无法计算。"""

    report = get_ad_report(campaign_id)  # 复用已有查询函数。
    spend = report["spend"]  # 从报表字典读取花费。

    # 根据实际报表计算，避免除以0。
    if spend > 0:
        roas = round(report["attributed_sales"] / spend, 4)
        message = "计算完成"
    else:
        roas = None
        message = "广告花费为0，ROAS无法计算"

    return {
        "data_source": report["data_source"],  # 保留合成数据标记。
        "campaign_id": campaign_id,
        "spend": spend,
        "attributed_sales": report["attributed_sales"],
        "roas": roas,  # 当前样例为250÷100，结果2.5。
        "message": message,
    }


class InventoryInput(BaseModel):
    # 严格校验参数，并去掉字符串首尾空白。
    model_config = ConfigDict(
        strict=True,
        str_strip_whitespace=True,
    )

    sku: str = Field(
        min_length=1,  # 商品编号至少有一个字符。
        description="商品编号，例如SKU-DEMO-001",
    )

@tool("get_inventory", args_schema=InventoryInput)
def inventory_tool(sku: str) -> dict:
    """查询当前演示店铺的数据库库存，返回库存量、预警阈值及低库存标记。"""

    result = get_inventory_from_db(
        user_id="user-001",  # 当前本地演示用户，正式接登录后由后端取得。
        store_id="store-A",  # 当前本地演示店铺，查询函数会检查所属用户。
        sku=sku,  # 模型提供的商品编号，InventoryInput先检查参数类型。
    )

    if result is None:
        raise ValueError("未找到可访问的商品库存")
        # 原来的工具执行循环会捕获ValueError，返回查询失败信息。

    return result
    # 返回数据库里的库存、阈值、低库存判断及version。
