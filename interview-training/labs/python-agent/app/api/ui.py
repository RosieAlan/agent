import logging

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import (
    OperationalError,
    SQLAlchemyError,
    TimeoutError as PoolTimeoutError,
)

from app.schemas.ui import UIResponse
from app.services.ui_service import (
    build_ad_report_ui,
    AdReportNotFound,
)

router = APIRouter(prefix="/ui", tags=["ui"])
logger = logging.getLogger(__name__)


@router.get(
    "/ads/report/{campaign_id}",
    response_model=UIResponse,
)
def ad_report_ui(campaign_id: str):
    try:
        return build_ad_report_ui(
            user_id="user-001",  # 当前本地演练身份。
            store_id="store-A",  # 当前演练店铺。
            campaign_id=campaign_id,  # URL中的广告编号。
        )

    except AdReportNotFound as error:
        raise HTTPException(
            404,
            "未找到可访问的广告报表",
        ) from error

    except (OperationalError, PoolTimeoutError) as error:
        raise HTTPException(
            503,
            "报表数据库暂时不可用",
        ) from error

    except SQLAlchemyError as error:
        logger.exception("UI report database query failed")
        raise HTTPException(
            500,
            "报表查询失败",
        ) from error

    except ValidationError as error:
        logger.exception("UI report structure invalid")
        raise HTTPException(
            500,
            "展示数据格式异常",
        ) from error