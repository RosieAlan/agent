import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from app.core.errors import DependencyUnavailable


@lru_cache
def get_model():
    # 创建模型客户端时读取本机配置；这里尚未发送模型请求。
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    names = ["OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL"]
    if any(not os.getenv(name) for name in names):
        raise DependencyUnavailable("模型配置缺失，请检查后端.env")
    return ChatOpenAI(model=os.environ["OPENAI_MODEL"],
        api_key=os.environ["OPENAI_API_KEY"], base_url=os.environ["OPENAI_BASE_URL"],
        temperature=0, timeout=25, max_retries=0, use_responses_api=False)
