import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.api.inventory import router as inventory_router
from app.core.errors import AccessDenied, AuthenticationFailed, DependencyUnavailable

# 应用入口只负责创建应用和装配接口，业务逻辑放在对应服务中。
app = FastAPI(title="运营提效助手")
app.include_router(health_router)  # 注册app/api/health.py中的接口。
app.include_router(auth_router, prefix="/api/v1")
app.include_router(inventory_router, prefix="/api/v1")


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, error: RequestValidationError):
    # 校验错误仅返回字段位置和原因，避免input或ctx回显密码、令牌。
    details = [{"loc": item["loc"], "type": item["type"], "msg": item["msg"]} for item in error.errors()]
    return JSONResponse(status_code=422, content={"detail": details}, headers={"Cache-Control": "no-store"})


@app.exception_handler(AuthenticationFailed)
async def authentication_failed(request: Request, error: AuthenticationFailed):
    return JSONResponse(status_code=401, content={"detail": "账号密码错误或登录已失效，请重新登录"}, headers={"WWW-Authenticate": "Bearer", "Cache-Control": "no-store"})


@app.exception_handler(AccessDenied)
async def access_denied(request: Request, error: AccessDenied):
    return JSONResponse(status_code=403, content={"detail": "当前账号没有该店铺的访问权限"})


@app.exception_handler(DependencyUnavailable)
async def dependency_unavailable(request: Request, error: DependencyUnavailable):
    logging.getLogger(__name__).warning("upstream_unavailable path=%s error_type=%s", request.url.path, type(error.__cause__).__name__)
    return JSONResponse(status_code=503, content={"detail": str(error)})
