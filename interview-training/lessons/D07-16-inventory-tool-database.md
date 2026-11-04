# D07：库存工具读取数据库，与广告查询统一。日期：11/04

前置：学生已提交广告Agent查询和ROAS工具完整输出，本块通过。当前库存HTTP读库20/20/version2，而Agent库存工具仍为常量12，需要复用已有仓储函数。

调用链：POST /ads/chat → main.ad_chat → llm_service.run_ad_tool → 模型返回get_inventory及sku → 后端执行ad_tools.inventory_tool → inventory_repository.get_inventory_from_db → PostgreSQL → ToolMessage → 模型答复。db.py管理连接池，models.py描述表；本块继续使用原库存表，无新迁移。

ad_tools.py顶部新增导入，原InventoryInput、工具绑定、工具白名单与线程执行继续复用：

```python
from inventory_repository import get_inventory_from_db  # 复用已经写好的数据库查询。
```

找到带@tool的inventory_tool，替换整个函数及装饰器：

```python
@tool("get_inventory", args_schema=InventoryInput)
def inventory_tool(sku: str) -> dict:
    """查询当前演示店铺的数据库库存，返回库存量、预警阈值及低库存标记。"""

    result = get_inventory_from_db(
        user_id="user-001",  # 当前本地演示身份；生产由验证后的登录状态提供。
        store_id="store-A",  # 当前本地演示店铺；查询同时检查用户归属。
        sku=sku,  # 模型提供业务编号，Schema先检查其类型。
    )

    if result is None:
        raise ValueError("未找到可访问的商品库存")  # 原工具循环处理查无数据。

    return result  # 库存、阈值、低库存标记及version都来自已有查询函数。
```

main.py的ad_chat两个数据库异常分支，将detail改为“业务数据库暂时不可用”和“业务数据查询失败，请联系维护人员”，原状态码503/500继续。直接报表GET仍使用报表专用提示。

工具说明来自函数docstring，模型能看到其名称、参数Schema和说明。更新说明使模型知道阈值来自查询结果。库存比较stock < threshold在仓储函数中完成，模型据此解释。

浏览器GET http://127.0.0.1:8000/inventory/SKU-DEMO-001查看当前值；Swagger POST /ads/chat输入“查询SKU-DEMO-001当前库存，说明预警阈值、是否低库存和数据来源。只查询。” 工具结果应与GET一致。本轮教师只读结果stock20/threshold20/is_low_stock false/version2；后续修改后以实际GET为准。已有服务重启后重新加载工具定义；当前教师启动无reload，学生用终端reload启动前须停止8000旧服务，避免端口冲突。

失败：未知SKU→已有循环data_not_found；数字sku→invalid_arguments；数据库连接/池等待失败→503。默认后端作用域避免由模型直接选择其他用户身份；生产JWT和动态店铺权限仍待接入，本地固定值不计真实认证完成。当前仅查询，库存修改工具、审批和通知未开放。

必背：业务查询写在repository，HTTP接口和Agent工具调用同一查询函数，因此可共享数据来源、权限条件和业务判断。模型提出工具调用，后端执行数据库查询，再把结果交给模型回答。

已验证：广告实际工具100/250及2.5；库存候选与数据库20/20/version2一致、跨用户无命中、未知值和非法类型失败。无数据库写入和付费模型请求。学生库存Agent结果待交；后续任务执行记录/历史持久化和D07综合检查继续，完整独立通过1/32。
