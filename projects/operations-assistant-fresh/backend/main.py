import logging  # 记录后端错误。
from contextlib import asynccontextmanager  # 定义应用启动和停止阶段。

from fastapi import FastAPI, HTTPException, Request
from sqlalchemy import text  # 将SQL字符串转换成可执行语句。
from sqlalchemy.exc import SQLAlchemyError  # 捕获数据库操作异常。

from db import engine  # 使用db.py创建的引擎。

# from fastapi import Path  # 校验URL路径中的商品编号。
from fastapi import Query
from repositories.inventory import find_inventory  # 导入数据库查询函数。
from schemas.inventory import (
    InventoryResponse,
    InventoryCheckResponse,
)  # 导入响应格式。
from fastapi import Query  # 校验URL问号后面的查询参数。

# from services.inventory import inspect_inventory
from services import inspect_inventory  # 从services包入口导入业务函数。
import asyncio

from openai import APIError

from schemas.assistant import AssistantInput, ToolPlanResponse
from services.assistant import plan_inventory_tool

from openai import APITimeoutError
from pydantic import ValidationError

from uuid import UUID, uuid4
from pymysql import MySQLError
from core.checkpoints import checkpoint_resources
from graphs.inventory import create_inventory_graph
from schemas.assistant import TaskAnswer, TaskStatus
from services.inventory_tasks import InventoryTasks, TaskNotFound, TaskBusy

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        async with checkpoint_resources() as (pool, saver):
            # 启动时创建一次持久化图，各请求共用同一个连接池。
            app.state.inventory_tasks = InventoryTasks(create_inventory_graph(saver), pool)
            yield
    finally:
        engine.dispose()  # 应用停止时关闭业务查询连接池。


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
    "/inventory",
    response_model=InventoryResponse,  # 校验并整理HTTP响应。
)
def inventory_detail(
    sku: str = Query(..., min_length=1, max_length=64),
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


@app.get(
    "/inventory/check",
    response_model=InventoryCheckResponse,
)
def inventory_check(
    sku: str = Query(..., min_length=1, max_length=64),
    threshold: int = Query(default=20, ge=0, le=1_000_000),
):
    try:
        result = inspect_inventory(sku, threshold)  # 执行查询和业务判断。

    except SQLAlchemyError as error:
        logger.exception("库存检查失败")

        raise HTTPException(
            status_code=503,
            detail="库存数据库暂时不可用",
        ) from error

    if not result["items"]:
        raise HTTPException(
            status_code=404,
            detail="未找到该商品的库存记录",
        )

    return result


@app.post("/assistant/plan", response_model=ToolPlanResponse)
async def assistant_plan(body: AssistantInput):
    try:
        # 限制这一整个处理过程的等待时间。
        async with asyncio.timeout(30):
            return await plan_inventory_tool(body.input)

    except TimeoutError as error:
        raise HTTPException(
            status_code=504,
            detail="模型响应超时，请稍后重试",
        ) from error

    except APIError as error:
        logger.exception("模型工具选择失败")

        raise HTTPException(
            status_code=502,
            detail="模型服务调用失败，请查看后端日志",
        ) from error

def task_service(request: Request) -> InventoryTasks:
    return request.app.state.inventory_tasks  # 读取启动时创建的持久化图服务。


async def execute_inventory_task(request: Request, task_id: str, input_text: str | None = None):
    try:
        # 等待上限覆盖排队、模型、工具、评审和检查点写入。
        async with asyncio.timeout(60):
            return await task_service(request).run(task_id, input_text)
    except TaskNotFound as error:
        raise HTTPException(404, detail={"task_id": task_id, "message": str(error)}) from error
    except TaskBusy as error:
        raise HTTPException(409, detail={"task_id": task_id, "message": str(error)}) from error
    except (TimeoutError, APITimeoutError) as error:
        raise HTTPException(504, detail={"task_id": task_id, "message": "任务超时，可查询已保存进度后恢复"}) from error
    except (SQLAlchemyError, MySQLError) as error:
        logger.exception("库存任务数据库操作失败 task_id=%s", task_id)
        raise HTTPException(503, detail={"task_id": task_id, "message": "数据库暂时不可用，请恢复连接后查询任务"}) from error
    except (APIError, ValidationError, RuntimeError) as error:
        logger.exception("库存任务执行失败 task_id=%s", task_id)
        raise HTTPException(502, detail={"task_id": task_id, "message": "模型或任务执行失败，可查询进度并恢复"}) from error


@app.post("/assistant/chat", response_model=TaskAnswer)
async def assistant_chat(body: AssistantInput, request: Request):
    task_id = str(uuid4())  # 每个新问题获得独立编号，原任务沿用原编号恢复。
    return await execute_inventory_task(request, task_id, body.input)


@app.get("/assistant/task", response_model=TaskStatus)
async def assistant_task(request: Request, task_id: UUID = Query(...)):
    try:
        async with asyncio.timeout(10):
            return await task_service(request).read(str(task_id))
    except TaskNotFound as error:
        raise HTTPException(404, detail="未找到已保存的任务") from error
    except (TimeoutError, MySQLError) as error:
        logger.exception("检查点查询失败")
        raise HTTPException(503, detail="任务状态暂时无法读取") from error


@app.post("/assistant/resume", response_model=TaskAnswer)
async def assistant_resume(request: Request, task_id: UUID = Query(...)):
    # 恢复时沿用原编号，由检查点读回消息和已执行轮数。
    return await execute_inventory_task(request, str(task_id))
