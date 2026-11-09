import logging  # 记录后端错误。
import json
from schemas.assistant import ConfirmationInput  # 校验用户提交的选择。
from services.inventory_tasks import TaskConflict  # 当前状态不允许确认时返回409。
from fastapi.responses import StreamingResponse
from services.streaming import stream_inventory
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
import time

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
from schemas.supervisor import SupervisorInput, SupervisorPlan
from services.supervisor import select_experts
from graphs.team import team_graph
from schemas.supervisor import TeamResponse
from services.knowledge import preview_sop_chunks  # 导入SOP分块函数。
from services.knowledge import MAX_DOCUMENT_BYTES, parse_uploaded_document
from schemas.knowledge import DocumentPreview
from schemas.knowledge import DocumentSearchResponse
from services.knowledge_search import EmbeddingNotConfigured, search_document
from fastapi import UploadFile, Form
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool
from pathlib import Path as FilePath
from api.knowledge import router as knowledge_router
from core.knowledge_db import close_knowledge_engine
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        async with checkpoint_resources() as (pool, saver):
            # 启动时创建一次持久化图，各请求共用同一个连接池。
            app.state.inventory_tasks = InventoryTasks(
                create_inventory_graph(saver), pool
            )
            yield
    finally:
        engine.dispose()  # 应用停止时关闭业务查询连接池。
        close_knowledge_engine()  # 一并归还知识库连接池资源。


app = FastAPI(
    title="运营提效助手",
    lifespan=lifespan,  # 注册应用生命周期处理。
)
app.include_router(knowledge_router)  # 知识库接口按模块注册，main.py保留启动入口。


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "project": "运营提效助手",
    }


@app.post("/assistant/supervisor", response_model=SupervisorPlan)
async def assistant_supervisor(body: SupervisorInput):
    """D11：先单独验证专家选择，后续接入多专家图。"""
    try:
        async with asyncio.timeout(30):  # 为这次专家选择设置总等待上限。
            return await select_experts(body.input)  # 用户问题→名单和选择理由。
    except (TimeoutError, APITimeoutError) as error:
        raise HTTPException(504, detail="专家选择超时，请稍后重试") from error
    except (APIError, ValidationError, RuntimeError) as error:
        logger.exception("专家选择失败")  # 技术细节留在后端日志。
        raise HTTPException(502, detail="专家选择暂时失败，请查看后端日志") from error


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


async def execute_inventory_task(
    request: Request,
    task_id: str,
    input_text: str | None = None,
    approved: bool | None = None,  # 新增：None表示本次没有提交确认选择。
    require_confirmation: bool = False,  # 新任务的执行前确认开关。
):
    try:
        async with asyncio.timeout(60):
            tasks = task_service(request)  # 取得启动时创建的任务服务。

            if approved is not None:
                return await tasks.confirm(
                    task_id,
                    approved,
                )  # True和False都进入确认处理。

            return await tasks.run(
                task_id,
                input_text,
                require_confirmation=require_confirmation,
            )  # 沿用原来的新任务和失败恢复逻辑。

    except TaskNotFound as error:
        raise HTTPException(
            404, detail={"task_id": task_id, "message": str(error)}
        ) from error
    except (TaskBusy, TaskConflict) as error:
        raise HTTPException(
            409, detail={"task_id": task_id, "message": str(error)}
        ) from error
    except (TimeoutError, APITimeoutError) as error:
        raise HTTPException(
            504,
            detail={"task_id": task_id, "message": "任务超时，可查询已保存进度后恢复"},
        ) from error
    except (SQLAlchemyError, MySQLError) as error:
        logger.exception("库存任务数据库操作失败 task_id=%s", task_id)
        raise HTTPException(
            503,
            detail={
                "task_id": task_id,
                "message": "数据库暂时不可用，请恢复连接后查询任务",
            },
        ) from error
    except (APIError, ValidationError, RuntimeError) as error:
        logger.exception("库存任务执行失败 task_id=%s", task_id)
        raise HTTPException(
            502,
            detail={
                "task_id": task_id,
                "message": "模型或任务执行失败，可查询进度并恢复",
            },
        ) from error


@app.post("/assistant/chat", response_model=TaskAnswer | TaskStatus)
async def assistant_chat(body: AssistantInput, request: Request):
    task_id = str(uuid4())  # 每个新问题获得独立编号，原任务沿用原编号恢复。
    return await execute_inventory_task(
        request,
        task_id,
        body.input,
        require_confirmation=body.require_confirmation,
    )  # 等待确认时返回TaskStatus；完成时沿用TaskAnswer。


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


@app.post("/assistant/resume", response_model=TaskAnswer | TaskStatus)
async def assistant_resume(request: Request, task_id: UUID = Query(...)):
    # 恢复时沿用原编号，由检查点读回消息和已执行轮数。
    return await execute_inventory_task(request, str(task_id))


@app.post("/assistant/confirm", response_model=TaskStatus)
async def assistant_confirm(
    body: ConfirmationInput,  # 从JSON读取approved。
    request: Request,
    task_id: UUID = Query(...),  # 从查询参数读取原任务编号，并校验UUID格式。
):
    return await execute_inventory_task(
        request,
        str(task_id),
        approved=body.approved,  # 将用户选择传给任务服务。
    )


@app.post("/assistant/stream")
async def assistant_stream(body: AssistantInput, request: Request):
    task_id = str(uuid4())  # 沿用已有的编号生成方式。
    tasks = task_service(request)  # 取得已有任务服务。

    async def generate():
        async for event in stream_inventory(
            tasks,
            task_id,
            body.input,
            body.require_confirmation,
        ):
            # 将字典转为JSON，并按SSE格式发送；空行表示一条事件结束。
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),  # 持续提供事件内容。
        media_type="text/event-stream",  # 声明响应为SSE。
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # 告诉Nginx关闭此响应的代理缓冲。
        },
    )


@app.post("/assistant/team", response_model=TeamResponse)
async def assistant_team(
    body: SupervisorInput,  # JSON中接收用户问题。
    sku: str = Query(..., min_length=1, max_length=64),
    threshold: int = Query(default=20, ge=0, le=1_000_000),
):
    try:
        async with asyncio.timeout(60):  # 限制整个分析流程的等待时间。
            result = await team_graph.ainvoke(
                {
                    "input": body.input,
                    "sku": sku,
                    "threshold": threshold,
                    "deadline": time.monotonic() + 60,  # 让评审使用请求剩余时间。
                }
            )

            # 明确选择对外返回的字段，图内部facts保留在流程中。
            return TeamResponse(
                experts=result["experts"],
                reason=result["reason"],
                status=result["status"],
                answer=result["answer"],
                inventory_report=result["inventory_report"],
                replenishment_report=result["replenishment_report"],
                expert_errors=result["expert_errors"],  # 告诉前端哪些专家尚未完成。
                quality_status=result["quality_status"],
                review_issues=result["review_issues"],
                revise_count=result["revise_count"],
            )

    except (TimeoutError, APITimeoutError) as error:
        logger.exception("多专家分析超时")  # 保留异常栈及LangGraph失败节点，便于定位。
        raise HTTPException(
            504,
            detail="专家分析超时，请稍后重试",
        ) from error

    except SQLAlchemyError as error:
        logger.exception("多专家库存查询失败")
        raise HTTPException(
            503,
            detail="库存数据库暂时不可用",
        ) from error

    except (APIError, ValidationError, RuntimeError) as error:
        logger.exception("多专家分析失败")
        raise HTTPException(
            502,
            detail="专家分析失败，请查看后端日志",
        ) from error
@app.get("/knowledge/preview")
def knowledge_preview() -> dict:
    try:
        # 请求到达时，读取SOP并返回分块结果。
        return preview_sop_chunks()

    except FileNotFoundError as error:
        # 文件路径对应的SOP尚未保存。
        raise HTTPException(
            404,
            detail="SOP文件尚未保存",
        ) from error

    except (UnicodeDecodeError, ValueError) as error:
        # 编码错误或文档内容为空。
        raise HTTPException(
            422,
            detail="请检查SOP内容和UTF-8编码",
        ) from error


@app.get("/knowledge", response_class=FileResponse)
def knowledge_upload_page():
    # 页面与接口同源，浏览器直接调用当前Python服务。
    return FileResponse(FilePath(__file__).parent / "web" / "knowledge.html")


@app.get("/knowledge/sample", response_class=FileResponse)
def knowledge_sample():
    from services.knowledge import SOURCE_FILE
    return FileResponse(SOURCE_FILE, filename=SOURCE_FILE.name)


@app.post("/knowledge/upload", response_model=DocumentPreview, tags=["knowledge"])
async def knowledge_upload(file: UploadFile):
    # UploadFile接收浏览器选择的文件，包含文件名和文件内容。
    try:
        content = await file.read(MAX_DOCUMENT_BYTES + 1)  # 有界读取，避免全文载入超大文件。
        if len(content) > MAX_DOCUMENT_BYTES:
            raise HTTPException(413, detail="文件超过2MiB限制")
        # 文本切分在线程池执行，让其他异步请求继续处理。
        return await run_in_threadpool(
            parse_uploaded_document, file.filename or "", content,
        )
    except UnicodeDecodeError as error:
        raise HTTPException(422, detail="文件编码需为UTF-8，请另存后重新上传") from error
    except ValueError as error:
        raise HTTPException(422, detail=str(error)) from error
    finally:
        await file.close()  # 成功和失败均关闭上传产生的临时文件。


@app.post("/knowledge/search-preview", response_model=DocumentSearchResponse, tags=["knowledge"])
async def knowledge_search_preview(file: UploadFile, query: str = Form(min_length=1, max_length=2000)):
    try:
        query = query.strip()
        if not query:
            raise HTTPException(422, detail="请输入要检索的问题")
        # 沿用上一块上传校验与解析函数，得到文字块及其来源。
        preview = await knowledge_upload(file)
        if preview["chunk_count"] > 100:
            raise HTTPException(422, detail="本次预览最多支持100块，请拆分文档后重试")
        return await search_document(preview, query)
    except EmbeddingNotConfigured as error:
        raise HTTPException(503, detail=str(error)) from error
    except (APITimeoutError, TimeoutError) as error:
        raise HTTPException(504, detail="向量服务响应超时，请稍后重试") from error
    except APIError as error:
        logger.warning("向量接口失败 status=%s", getattr(error, "status_code", None))
        raise HTTPException(502, detail="向量接口调用失败，请核对Embedding模型、地址、余额与密钥") from error
    except (ValueError, RuntimeError) as error:
        raise HTTPException(502, detail="文档检索预览失败，请检查文档规模与模型返回") from error
    finally:
        await file.close()  # 空问题及上游异常时也释放上传资源。
