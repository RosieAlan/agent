"""Langfuse配置：显式开启后，将已选业务链的观测记录发往配置的项目。"""

from functools import lru_cache
import os
from urllib.parse import urlsplit

from langfuse import get_client
from langfuse.langchain import CallbackHandler


@lru_cache(maxsize=1)
def tracing_client():
    # 配置变更后重启进程；同一进程复用SDK客户端及后台上报资源。
    if os.getenv("LANGFUSE_ENABLED", "false").lower() != "true":
        return None
    required = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_BASE_URL")
    if any(not os.getenv(name, "").strip() for name in required):
        raise RuntimeError("请完整配置LANGFUSE_PUBLIC_KEY、LANGFUSE_SECRET_KEY、LANGFUSE_BASE_URL")
    address = urlsplit(os.environ["LANGFUSE_BASE_URL"])
    if address.scheme not in ("http", "https") or not address.hostname:
        raise RuntimeError("LANGFUSE_BASE_URL必须为完整的HTTP或HTTPS地址")
    return get_client()  # SDK读取上述环境变量，初始化项目连接。


def langfuse_config(name: str) -> dict:
    """提供给Runnable.ainvoke的配置；关闭时继续使用原有调用行为。"""
    if tracing_client() is None:
        return {}
    return {
        "run_name": name,  # Langfuse页面中用于识别本次业务链。
        "callbacks": [CallbackHandler(public_key=os.environ["LANGFUSE_PUBLIC_KEY"])],
        "metadata": {"data_source": "synthetic_demo"},
    }  # 每次业务调用创建独立回调，SDK客户端共用。
