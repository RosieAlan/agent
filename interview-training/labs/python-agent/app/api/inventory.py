from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from app.schemas.inventory import InventoryUpdateInput
from app.repositories.inventory_repository import (get_inventory_from_db, update_inventory_in_db, InventoryConflictError)

router = APIRouter(tags=["inventory"])  # 收集库存接口。


@router.get("/inventory/{sku}")  # 当前本地演示入口：按商品编号查询库存。
def inventory_detail(sku: str):
    try:
        result = get_inventory_from_db(
            user_id="user-001",  # 本地演示身份；后续从登录凭据取得。
            store_id="store-A",  # 本地演示店铺；后续校验店铺访问权限。
            sku=sku,  # 使用URL中的商品编号。
        )

    except OperationalError as error:
        raise HTTPException(
            status_code=503,
            detail="数据库暂时无法访问",
        ) from error

    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=500,
            detail="库存查询失败，请检查后端和数据库结构",
        ) from error  # 例如初始化遗漏导致表不存在。

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="未找到可访问的商品库存",
        )

    return result  # 将查询结果交给FastAPI，转换成JSON响应。



@router.patch("/inventory/{sku}")
def inventory_update(sku: str, body: InventoryUpdateInput):
    try:
        result = update_inventory_in_db(
            user_id="user-001",  # 沿用当前本地演示身份。
            store_id="store-A",
            sku=sku,
            stock=body.stock,
            expected_version=body.expected_version,  # 新增参数。
        )

    except InventoryConflictError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error  # 版本过期，提示用户刷新确认。

    except OperationalError as error:
        raise HTTPException(
            status_code=503,
            detail="数据库暂时无法访问",
        ) from error

    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=500,
            detail="库存修改失败，请检查后端和数据库结构",
        ) from error

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="未找到可修改的商品库存",
        )

    return result  # 返回修改后的库存和新版本号。
