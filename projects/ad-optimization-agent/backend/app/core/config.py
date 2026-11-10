from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class SourceSettings:
    host: str
    port: int
    database: str
    user: str
    password: str


@lru_cache(maxsize=1)
def source_settings() -> SourceSettings:
    # 明确读取第二项目backend/.env；配置变更后重启进程。
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    keys = ("HOST", "PORT", "NAME", "USER", "PASSWORD")
    if any(not os.getenv(f"SOURCE_DB_{key}") for key in keys):
        raise RuntimeError("请完整配置SOURCE_DB_HOST/PORT/NAME/USER/PASSWORD")
    return SourceSettings(
        host=os.environ["SOURCE_DB_HOST"],
        port=int(os.environ["SOURCE_DB_PORT"]),
        database=os.environ["SOURCE_DB_NAME"],
        user=os.environ["SOURCE_DB_USER"],
        password=os.environ["SOURCE_DB_PASSWORD"],
    )
