import json
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import Settings, get_settings
from app.core.errors import AuthenticationFailed, DependencyUnavailable
from app.integrations.company_sso import CompanySSO
from app.schemas.auth import AuthContext, CurrentUser, LoginInput, LoginOutput


class AuthService:
    def __init__(self, settings: Settings, sso: CompanySSO):
        self.settings = settings
        self.sso = sso
        # 将公司token和已验证的user_id加密绑定，客户端无法修改或读取。
        self.cipher = Fernet(settings.session_key.encode("ascii"))

    @staticmethod
    def _user(data: dict, expected_id: str) -> CurrentUser:
        # 账号有效性由公司SSO认证；本地核对返回身份与已绑定身份一致。
        if str(data.get("userId", "")) != expected_id:
            raise AuthenticationFailed()
        name = data.get("userName")
        if not isinstance(name, str) or not name:
            raise DependencyUnavailable("公司身份响应缺少用户名")
        # 白名单映射：公司返回的密码字段、电话、API密钥均不会转发。
        return CurrentUser(id=expected_id, username=name, display_name=data.get("fullName") or name)

    def login(self, body: LoginInput) -> LoginOutput:
        username = body.username.strip()
        if not username:
            raise AuthenticationFailed()
        result = self.sso.login(username, body.password.get_secret_value())
        user_id, token = result.get("userId"), result.get("token")
        if isinstance(user_id, bool) or not isinstance(user_id, (str, int)) or not str(user_id) or not isinstance(token, str) or not token or len(token) > 4096:
            raise DependencyUnavailable("公司登录响应缺少身份或会话")
        user = self._user(self.sso.user_info(token, str(user_id)), str(user_id))
        payload = json.dumps({"user_id": user.id, "company_token": token}, separators=(",", ":")).encode("utf-8")
        access_token = self.cipher.encrypt(payload).decode("ascii")
        return LoginOutput(access_token=access_token, expires_in=self.settings.session_ttl, user=user)

    def authenticate(self, access_token: str) -> AuthContext:
        try:
            payload = json.loads(self.cipher.decrypt(access_token.encode("ascii"), ttl=self.settings.session_ttl))
            user_id, token = payload["user_id"], payload["company_token"]
            if not isinstance(user_id, str) or not isinstance(token, str) or not user_id or not token:
                raise ValueError("Invalid session fields")
        except (InvalidToken, UnicodeError, ValueError, TypeError, KeyError) as error:
            raise AuthenticationFailed() from error
        # 每次请求重新验证公司会话及当前权限，角色撤销可及时生效。
        user = self._user(self.sso.user_info(token, user_id), user_id)
        permissions = self.sso.permissions(token, user_id)
        if str(permissions.get("userId", "")) != user_id:
            raise AuthenticationFailed()
        codes = permissions.get("accountList")
        if codes is None:
            codes = []  # 缺少明确账号授权时返回空范围。
        if not isinstance(codes, list) or any(not isinstance(code, str) or not code.strip() for code in codes):
            raise DependencyUnavailable("公司店铺授权格式异常")
        return AuthContext(user=user, account_codes=sorted(set(codes)))


@lru_cache
def get_auth_service() -> AuthService:
    settings = get_settings()
    return AuthService(settings, CompanySSO(settings))
