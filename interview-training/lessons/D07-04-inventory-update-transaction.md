# D07：库存更新与事务提交。日期：11/02

当前/health/db学生运行通过，库存查询源码已实现，学生口述ok；库存GET实际JSON尚未提交。继续一条完整链：Swagger PATCH /inventory/{sku}→main.inventory_update(body)→inventory_repository.update_inventory_in_db→db.engine.begin→UPDATE FROM RETURNING→事务提交→返回记录，再通过原GET独立读取。实际身份仍本地固定user-001/store-A，生产鉴权待接入；本轮写操作由浏览器明确提交，Agent只读工具保持原样。

改动：inventory_repository.py在get_inventory_from_db之后、if __name__之前新增函数；main顶部增加导入update_inventory_in_db，末尾追加输入类和PATCH接口。BaseModel/ConfigDict/Field/HTTPException/SQLAlchemyError/OperationalError已导入，沿用。新增业务代码由学生写入。

必备：UPDATE SET更新指定列；FROM联合店铺限定用户归属；RETURNING返回本次更新后的记录；engine.begin成功提交/异常回滚并归还连接；返回语句位于with之外，提交失败会传播异常。当前同步路由在线程池执行。PATCH在本课把库存设为绝对值，库存扣减/并发覆盖及版本控制在D07后续继续。extra=forbid拒绝请求额外字段，strict拒绝字符串/布尔冒充整数，ge/le限定PG INTEGER非负范围。

仓储增量：

```python
def update_inventory_in_db(
    user_id: str, store_id: str, sku: str, stock: int
) -> dict | None:
    """把指定用户、店铺、商品的库存改为传入数量。"""
    with engine.begin() as connection:  # 正常结束提交；异常时自动回滚。
        row = connection.execute(
            text("""
                UPDATE inventory AS i
                SET stock = :stock
                FROM stores AS s
                WHERE s.id = i.store_id
                  AND s.user_id = :user_id
                  AND i.store_id = :store_id
                  AND i.sku = :sku
                RETURNING i.data_source, i.store_id, i.sku, i.stock, i.threshold
            """),  # 修改符合归属条件的库存，并取得修改后的记录。
            {
                "user_id": user_id,
                "store_id": store_id,
                "sku": sku,
                "stock": stock,
            },  # 参数继续单独传入。
        ).mappings().one_or_none()  # 没有可修改记录时得到None。

    # 走到这里，事务已提交成功，连接也已归还。
    if row is None:
        return None

    result = dict(row)  # 转成HTTP层可以返回的字典。
    result["is_low_stock"] = result["stock"] < result["threshold"]
    return result
```

main导入`from inventory_repository import update_inventory_in_db`，末尾增量：

```python
class InventoryUpdateInput(BaseModel):  # 本接口专用的请求格式。
    model_config = ConfigDict(strict=True, extra="forbid")  # 严格类型，拒绝额外字段。
    stock: int = Field(ge=0, le=2_147_483_647)  # PostgreSQL INTEGER的非负范围。


@app.patch("/inventory/{sku}")  # PATCH表示修改资源的部分字段。
def inventory_update(sku: str, body: InventoryUpdateInput):
    try:
        result = update_inventory_in_db(
            user_id="user-001",  # 沿用当前本地演示身份。
            store_id="store-A",  # 沿用当前本地演示店铺。
            sku=sku,  # URL中的商品编号。
            stock=body.stock,  # 通过校验的新库存。
        )
    except OperationalError as error:
        raise HTTPException(
            status_code=503, detail="数据库暂时无法访问"
        ) from error
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=500, detail="库存修改失败，请检查后端和数据库结构"
        ) from error

    if result is None:
        raise HTTPException(status_code=404, detail="未找到可修改的商品库存")
    return result  # 返回数据库修改后的记录。
```

Swagger http://127.0.0.1:8000/docs 选择PATCH /inventory/{sku}→Try it out→sku填SKU-DEMO-001→Body填{"stock":25}→Execute，预期200/stock25/is_low_stock false；原GET /inventory/SKU-DEMO-001再读应为25。Body stock=-1和stock="25"预期422，查库仍25；不存在SKU预期404。用户重复初始化时ON CONFLICT DO NOTHING保留已修改库存。原ad_tools.inventory_tool仍返回常量12，数据库查询接回Agent安排后续，当前验证通过HTTP入口完成。

必背完整答案：engine.begin把with中的SQL放入同一事务；正常结束提交，异常时回滚，退出后归还连接。接口校验拦截非法输入，数据库约束继续保护直接SQL写入。事务防止一组操作只完成一部分，并发更新仍需额外的条件更新/锁/版本策略。

教师验证：先确认更新函数缺失；候选在真实PG独立临时schema实测提交后新连接读25、越权更新无命中、B店88保持、未知SKU、负库存失败保持25、多语句事务第二步失败回滚第一步。HTTP200/404及负数/字符串/布尔/溢出/额外字段422。所有测试schema和数据已清理，并查询确认schema消失。教师未修改学生业务源码，供应商请求0次；学生PATCH/GET结果待交。

原课程对应5.3/数据库访问与事务基础；后续ORM与Alembic迁移、完整会话任务/Wiki模型、索引连接池与并发仍保留。官方：https://www.postgresql.org/docs/16/sql-update.html 、https://docs.sqlalchemy.org/en/21/core/connections.html#connect-and-begin-once-from-the-engine 。

