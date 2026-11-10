import os
from pathlib import Path

from dotenv import load_dotenv
from redis import Redis
from redis.backoff import NoBackoff
from redis.retry import Retry

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# 每个进程共用一个客户端及连接池；省略REDIS_URL时继续直接查MySQL。
redis_url = os.getenv("REDIS_URL", "").strip()
redis_client = Redis.from_url(
    redis_url,
    decode_responses=True,  # GET返回Python字符串，后续交给json解析。
    socket_connect_timeout=0.3,  # Redis故障时尽快回到MySQL查询。
    socket_timeout=0.3,
    max_connections=10,
    retry=Retry(NoBackoff(), 0),  # 缓存请求使用零次自动重试，控制额外等待。
) if redis_url else None


def close_cache() -> None:
    if redis_client is not None:
        redis_client.close()  # 后端关闭时释放Redis连接池。
