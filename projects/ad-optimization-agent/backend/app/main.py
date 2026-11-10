from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.api.ads import router as ads_router
from app.api.assistant import router as assistant_router
from app.db.source import source_engine, source_health

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        yield
    finally:
        source_engine.dispose()  # 服务退出时释放第二项目自己的连接池。


app = FastAPI(title="智能投放与多Agent创作平台", version="0.1.0", lifespan=lifespan)
app.include_router(ads_router)  # 将/ads下的接口注册到应用。
app.include_router(assistant_router)  # 新增：规划预览入口/assistant/plan。


@app.get("/health/live", tags=["健康检查"])
def live():
    return {"status": "ok", "project": "ad-optimization-agent"}


@app.get("/health/source", tags=["健康检查"])
def check_source():
    try:
        return source_health()  # 实际查询源数据库，并读取当前连接的只读标志。
    except SQLAlchemyError as error:
        logger.error("ad_source_unavailable error_type=%s", type(error).__name__)
        raise HTTPException(503, detail="广告数据源暂时不可用") from None
