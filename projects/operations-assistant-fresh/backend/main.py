import logging  # 记录后端错误。
from contextlib import asynccontextmanager  # 定义应用启动和停止阶段。

from fastapi import FastAPI, HTTPException
from sqlalchemy import text  # 将SQL字符串转换成可执行语句。
from sqlalchemy.exc import SQLAlchemyError  # 捕获数据库操作异常。

from db import engine  # 使用db.py创建的引擎。
from fastapi import Path  # 校验URL路径中的商品编号。

from repositories.inventory import find_inventory  # 导入数据库查询函数。
from schemas.inventory import InventoryResponse  # 导入响应格式。

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield  # 应用在此期间接收并处理请求。
    engine.dispose()  # 应用停止时释放连接池中的空闲连接。


app = FastAPI(
    title="运营提效助手",
    lifespan=lifespan,  # 注册应用生命周期处理。
)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "project": "运营提效助手",
    }


@app.get("/health/db")
def database_health() -> dict:
    try:
        # 从连接池获取连接，离开with时自动归还。
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1")).scalar_one()

        return {
            "status": "ok",
            "database": "connected",
            "result": result,
        }

    except SQLAlchemyError as error:
        logger.exception("数据库健康检查失败")  # 详细原因记录到后端日志。

        raise HTTPException(
            status_code=503,
            detail="数据库暂时不可用",
        ) from error


@app.get(
    "/inventory/{sku}",
    response_model=InventoryResponse,  # 校验并整理HTTP响应。
)
def inventory_detail(
    sku: str = Path(min_length=1, max_length=64),  # 从URL中取商品编号。
):
    try:
        inventories = find_inventory(sku)  # 调用repository，执行三表查询。

    except SQLAlchemyError as error:
        logger.exception("库存查询失败")  # 详细错误留在后端日志。

        raise HTTPException(
            status_code=503,
            detail="库存数据库暂时不可用",
        ) from error

    if not inventories:  # 查询成功，但没有匹配的库存记录。
        raise HTTPException(
            status_code=404,
            detail="未找到该商品的库存记录",
        )

    return {
        "data_source": "synthetic_demo",
        "sku": sku,
        "items": inventories,
    }
