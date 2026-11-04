from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from app.db.session import check_database

router = APIRouter(tags=["health"])  # 收集健康检查接口。


@router.get("/health/db")  # 注册GET接口，浏览器可以直接访问。
def database_health():
    try:
        # main.py → db.py → PostgreSQL → 返回检查结果字典。
        return check_database()

    except SQLAlchemyError as error:
        # 数据库连接失败、连接池等待超时等情况，在这里转换为HTTP错误。
        raise HTTPException(
            status_code=503,  # 表示当前服务依赖的数据库暂时不可用。
            detail="数据库暂时无法连接，请检查数据库服务和连接配置",
        ) from error  # 保留原始异常关系，供后端排查。
