# D07-08 库存更新版本检查与HTTP409（2026-11-02）
一次成功更新把同一行version加1，当前列只保存最新计数；审计历史需单独表。失败冲突不递增。
原5.3事务和并发补充，当前继续Python后端主线。两个业务文件由学生修改，教师只验证候选并维护讲义。固定本地身份继续保留，正式认证仍待完成。
改动：仓储新增InventoryConflictError并替换update_inventory_in_db完整函数；main导入异常类，替换InventoryUpdateInput和库存PATCH函数，其他接口保留。
调用：PATCH输入stock/expected_version→Pydantic→仓储参数化SQL限定user/store/sku/version→同SQL更新stock和version+1→成功200；零行后作用域查询，无可访问记录404，有记录则抛冲突，main映射409。exception从with抛出时自动回滚。
在PostgreSQL默认READ COMMITTED下，竞争UPDATE等待前一事务并重新检查WHERE，版本过期者更新零行。数据库与事务仍使用行锁；当前演示称乐观锁是应用依靠版本检测冲突。
```python
class InventoryConflictError(Exception):
    pass  # 本项目定义的错误：库存版本已经变化。


def update_inventory_in_db(
    user_id: str,
    store_id: str,
    sku: str,
    stock: int,
    expected_version: int,  # 用户读取库存时拿到的版本号。
) -> dict | None:
    params = {
        "user_id": user_id,
        "store_id": store_id,
        "sku": sku,
        "stock": stock,
        "expected_version": expected_version,
    }

    with engine.begin() as connection:  # 全部成功后提交，异常时回滚。
        row = connection.execute(
            text("""
                UPDATE inventory AS i
                SET stock = :stock,
                    version = i.version + 1
                FROM stores AS s
                WHERE s.id = i.store_id
                  AND s.user_id = :user_id
                  AND i.store_id = :store_id
                  AND i.sku = :sku
                  AND i.version = :expected_version
                RETURNING i.data_source, i.store_id, i.sku,
                          i.stock, i.threshold, i.version
            """),  # 在同一条SQL中检查旧版本、修改库存并增加版本号。
            params,
        ).mappings().one_or_none()

        if row is None:
            exists = connection.execute(
                text("""
                    SELECT 1
                    FROM inventory AS i
                    JOIN stores AS s ON s.id = i.store_id
                    WHERE s.user_id = :user_id
                      AND i.store_id = :store_id
                      AND i.sku = :sku
                """),  # 更新零条时，区分商品不可访问和版本过期。
                params,
            ).scalar_one_or_none()

            if exists is None:
                return None  # HTTP层沿用404。
            raise InventoryConflictError(
                "库存已被修改，请刷新后确认"
            )  # HTTP层转换为409，本次事务回滚。

    result = dict(row)  # 成功提交后再返回结果。
    result["is_low_stock"] = result["stock"] < result["threshold"]
    return result
```
main顶部新增from inventory_repository import InventoryConflictError。
```python
class InventoryUpdateInput(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    stock: int = Field(ge=0, le=2_147_483_647)  # 新库存数量。
    expected_version: int = Field(
        ge=1, le=2_147_483_646
    )  # 读取时的版本；为数据库INTEGER递增保留空间。


@app.patch("/inventory/{sku}")
def inventory_update(sku: str, body: InventoryUpdateInput):
    try:
        result = update_inventory_in_db(
            user_id="user-001",  # 沿用当前本地演示身份。
            store_id="store-A",
            sku=sku,
            stock=body.stock,
            expected_version=body.expected_version,  # 新增：传给数据库函数。
        )
    except InventoryConflictError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error  # 版本过期，提示用户刷新确认。
    except OperationalError as error:
        raise HTTPException(
            status_code=503, detail="数据库暂时无法访问"
        ) from error
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=500, detail="库存修改失败，请检查后端和数据库结构"
        ) from error

    if result is None:
        raise HTTPException(
            status_code=404, detail="未找到可修改的商品库存"
        )
    return result  # 包含本次修改后的库存和新版本号。
```
浏览器先GET确认当前版本v，再PATCH stock20/expected_version=v，预期200/version=v+1；再次PATCH stock30/expected_version=v，预期409，GET仍20/v+1。随后刷新确认后可用最新版本提交。422覆盖漏版本/字符串版本/负库存，404未知SKU。
教师真实PG独立临时schema验证成功、旧版本冲突、跨用户不可更新、未知SKU、两真实并发连接恰好1成功+1冲突；HTTP200/409/404/422与B店库存88保持，事务提交后新连接核对。已清理schema并验证消失，课程库存全行前后相等，供应商调用0次。学生实作待交。
必背：更新时在同一SQL中匹配读取时版本，并递增版本。冲突409后刷新确认，再使用新版本提交；业务冲突需重新判断，盲目重试可能覆盖他人修改。需要全部写入口遵守同一协议。
此处实现绝对数量编辑保护，库存扣减、预留、流水与跨系统同步属于进一步业务设计。

