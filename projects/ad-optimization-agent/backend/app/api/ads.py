import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError

from app.repositories import ads as repo
from app.schemas.ads import AdProfile, AdReportResponse, ReportQuery
from app.services.ad_metrics import add_report_metrics

router = APIRouter(prefix="/ads", tags=["广告数据（只读）"])
logger = logging.getLogger("uvicorn.error")


@router.get("/profiles", response_model=list[AdProfile])
def profiles(limit: int = Query(default=50, ge=1, le=100)):
    try:
        return repo.list_profiles(limit)  # 同步SQL由FastAPI在线程池执行。
    except SQLAlchemyError as error:
        logger.error("ad_source_unavailable error_type=%s", type(error).__name__)
        raise HTTPException(503, detail="广告数据源暂时不可用") from None


@router.get("/reports", response_model=AdReportResponse)
def reports(query: Annotated[ReportQuery, Query()]):
    try:
        result = repo.fetch_reports(query)  # 校验后的查询参数传给数据访问层。
    except SQLAlchemyError as error:
        logger.error("ad_source_unavailable error_type=%s", type(error).__name__)
        raise HTTPException(503, detail="广告数据源暂时不可用") from None
    if result is None:
        raise HTTPException(404, detail="广告账户不存在")
    return add_report_metrics(result)  # 查询完成后计算指标，再交给响应Schema校验。
