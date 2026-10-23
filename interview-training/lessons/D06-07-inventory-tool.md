# D06：库存工具迁移。日期：10/23

沿原课3.8/4.3业务工具定义及tool-loop，将已学广告查询迁移到运营巡检，唯一入口/ads/chat沿用，后续统一工作台调整路由。SKU是商家区分商品的编号，本例SKU-DEMO-001为合成编号。工具参数由InventoryInput验证，后端根据12<20产生低库存布尔值。20为本课样例阈值。当前只查询和给建议，实际通知需要通知工具。

ad_tools.py末尾新增完整定义：

```python
class InventoryInput(BaseModel):
    model_config = ConfigDict(strict=True, str_strip_whitespace=True)
    sku: str = Field(min_length=1, description="商品编号，例如SKU-DEMO-001")


@tool("get_inventory", args_schema=InventoryInput)
def inventory_tool(sku: str) -> dict:
    """查询商品合成样例库存，返回库存量及是否低于本课样例阈值20件。"""
    if sku != "SKU-DEMO-001":
        raise ValueError("未找到该商品的样例库存")

    stock = 12  # 合成样例库存，后续改为数据库或授权接口查询。
    threshold = 20  # 本课样例规则，后续改为可配置业务规则。
    return {
        "data_source": "synthetic_demo",
        "sku": sku,
        "stock": stock,
        "threshold": threshold,
        "is_low_stock": stock < threshold,  # 后端比较数字，得到True或False。
    }
```

llm_service.py原工具导入和绑定整体替换：

```python
from ad_tools import ad_report_tool, calculate_roas_tool, inventory_tool
ad_tool_model = model.bind_tools([ad_report_tool, calculate_roas_tool, inventory_tool])
```

run_ad_tool内tools_by_name整块替换：

```python
    tools_by_name = {
        ad_report_tool.name: ad_report_tool,
        calculate_roas_tool.name: calculate_roas_tool,
        inventory_tool.name: inventory_tool,
    }
```

run_ad_tool系统消息content替换：

```python
"content": (
                "你是电商运营助手，数据来自合成样例，答复必须注明。"
                "查询广告使用get_ad_report，计算ROAS使用calculate_roas。"
                "查询库存使用get_inventory，根据返回的is_low_stock解释库存情况。"
                "广告编号或商品编号缺失时先询问，根据成功工具结果回答。"
                "库存不足时提供提醒建议，实际通知的发送需要另行接入通知工具。"
                "工具失败时说明失败，避免相同参数重复调用同一工具。"
                "投放是否有效需要结合目标ROAS、毛利和其他费用判断。"
),
```

错误通用化：ValidationError结果message改工具参数不符合要求，请检查字段及类型；ValueError结果error由report_not_found改data_not_found，message改未找到该编号对应的样例数据。当前未知广告编号验收同步使用data_not_found。

浏览器POST /ads/chat输入查询SKU-DEMO-001的库存，低于样例阈值时给出提醒建议。应get_inventory参数sku，stock12/threshold20/is_low_stock true，答复注明合成样例，实际通知发送无证据。独立改stock25再次查询，is_low_stock false。原缓存每请求新建，新一次请求读取新值。

必背：增加工具需定义参数和函数，绑定给模型，并加入后端执行字典；模型根据工具说明申请调用，后端校验与查询计算后回传。只绑定但未注册执行字典时当前程序返回unknown_tool。消息回填、缓存与轮次代码沿用。

本地真实工具+固定模型验证库存成功、非法参数、未知SKU、原广告/计算回归、库存25分支通过；供应商调用0次，学生运行待交。原课文件工具和路径限制下一块，失败检查保留补测。D06进行中，完整通过1/32。
