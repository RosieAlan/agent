from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.errors import AuthenticationFailed
from app.schemas.auth import AuthContext
from app.services.auth import AuthService, get_auth_service

bearer = HTTPBearer(auto_error=False)


def current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthContext:
    if credentials is None or len(credentials.credentials) > 16384:
        raise AuthenticationFailed()
    return service.authenticate(credentials.credentials)
