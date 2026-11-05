import base64
import re

import httpx
from cryptography.hazmat.primitives.asymmetric.padding import PKCS1v15
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.hazmat.primitives.serialization import load_der_public_key

from app.core.config import Settings
from app.core.errors import AuthenticationFailed, DependencyUnavailable


class CompanySSO:
    def __init__(self, settings: Settings):
        self.settings = settings
        # 兼容现有Vue登录的RSA协议，公钥从配置读取。
        self.public_key = load_der_public_key(base64.b64decode(re.sub(r"\s+", "", settings.sso_public_key)))
        if not isinstance(self.public_key, RSAPublicKey):
            raise ValueError("公司登录公钥必须为RSA公钥")

    def _request(self, method: str, path: str, *, token: str | None = None, login: bool = False, **kwargs) -> dict:
        # 每次调用独立的Cookie容器，避免不同用户共用上游会话。
        cookies = {"satoken": token} if token else {}
        try:
            with httpx.Client(base_url=self.settings.sso_base_url, timeout=8, trust_env=False, follow_redirects=False, cookies=cookies) as client:
                response = client.request(method, path, **kwargs)
            if response.status_code in {401, 403}:
                raise AuthenticationFailed()
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise DependencyUnavailable("公司认证服务暂时不可用") from error
        if not isinstance(body, dict):
            raise DependencyUnavailable("公司认证响应格式异常")
        code = body.get("code")
        if type(code) is not int:
            raise DependencyUnavailable("公司认证状态格式异常")
        if code not in {0, 200}:
            if login or str(body.get("errCode")) == "403":
                raise AuthenticationFailed()
            raise DependencyUnavailable("公司认证或权限响应异常")
        data = body.get("data")
        if not isinstance(data, dict):
            raise DependencyUnavailable("公司认证数据格式异常")
        return data

    def login(self, username: str, password: str) -> dict:
        raw_password = password.encode("utf-8")
        if len(raw_password) > self.public_key.key_size // 8 - 11:
            raise AuthenticationFailed()
        encrypted = base64.b64encode(self.public_key.encrypt(raw_password, PKCS1v15())).decode("ascii")
        return self._request("POST", "/cloud/sso/doLogin", login=True, files={"name": (None, username), "pwd": (None, encrypted)})

    def user_info(self, token: str, user_id: str) -> dict:
        return self._request("GET", "/cloud/kaidu/user/get/userInfo", token=token, params={"userId": user_id})

    def permissions(self, token: str, user_id: str) -> dict:
        return self._request("GET", "/cloud/kaidu/authorize/user/get", token=token, params={"userId": user_id})
