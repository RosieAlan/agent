from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.api.dependencies import current_user
from app.schemas.auth import AuthContext, CurrentUser, LoginInput, LoginOutput
from app.services.auth import AuthService, get_auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginOutput)
def login(body: LoginInput, response: Response, service: Annotated[AuthService, Depends(get_auth_service)]):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return service.login(body)


@router.get("/me", response_model=CurrentUser)
def me(context: Annotated[AuthContext, Depends(current_user)]):
    return context.user
