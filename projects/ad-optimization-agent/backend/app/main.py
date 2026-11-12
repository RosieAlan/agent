from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.api.ads import router as ads_router
from app.api.assistant import router as assistant_router
from app.api.proposals import router as proposals_router
from app.api.workflows import router as workflows_router
from app.api.harness import router as harness_router
from app.db.business import business_engine, business_health
from app.db.source import source_engine, source_health

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        yield
    finally:
        source_engine.dispose()  # 服务退出时释放第二项目自己的连接池。
        if business_engine.cache_info().currsize:
            business_engine().dispose()


app = FastAPI(title="智能投放与多Agent创作平台", version="0.1.0", lifespan=lifespan)
app.include_router(ads_router)  # 将/ads下的接口注册到应用。
app.include_router(assistant_router)  # 新增：规划预览入口/assistant/plan。
app.include_router(proposals_router)  # 草案及审批记录写入项目自有MySQL。
app.include_router(workflows_router)  # 图进度持久化与同一任务的人工恢复。
app.include_router(harness_router)  # DeepAgent清单、受限工具和虚拟报告文件。


@app.get("/health/live", tags=["健康检查"])
def live():
    return {"status": "ok", "project": "ad-optimization-agent"}


@app.get("/health/business", tags=["健康检查"])
def check_business():
    try:
        return business_health()
    except (SQLAlchemyError, RuntimeError):
        raise HTTPException(503, detail="项目业务数据库暂不可用") from None


@app.get("/health/source", tags=["健康检查"])
def check_source():
    try:
        return source_health()  # 实际查询源数据库，并读取当前连接的只读标志。
    except SQLAlchemyError as error:
        logger.error("ad_source_unavailable error_type=%s", type(error).__name__)
        raise HTTPException(503, detail="广告数据源暂时不可用") from None
