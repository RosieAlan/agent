import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    sso_base_url: str
    sso_public_key: str
    session_key: str
    session_ttl: int
    database_url: str = ""


@lru_cache
def get_settings() -> Settings:
    # 统一从backend/.env加载配置，进程环境变量优先。
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    base_url = os.environ["COMPANY_SSO_BASE_URL"].rstrip("/")
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("公司SSO地址配置无效")
    if os.getenv("APP_ENV", "development") == "production" and parsed.scheme != "https":
        raise ValueError("生产环境的公司SSO连接必须使用HTTPS")
    return Settings(
        sso_base_url=base_url,
        sso_public_key=os.environ["COMPANY_SSO_PUBLIC_KEY"],
        session_key=os.environ["SESSION_ENCRYPTION_KEY"],
        session_ttl=900,  # 本应用会话最长15分钟，访问时仍向公司系统验证。
        database_url=os.environ["DATABASE_URL"],
    )
