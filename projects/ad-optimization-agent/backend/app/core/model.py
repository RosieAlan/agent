"""第二项目独立模型客户端；收到规划请求后才创建。"""

from functools import lru_cache
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI


@lru_cache(maxsize=1)
def planning_model():
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    if os.getenv("OPENAI_MODEL") != "qwen3.8-flash":
        raise RuntimeError("规划器仅使用qwen3.8-flash")
    if not os.getenv("OPENAI_API_KEY") or not os.getenv("OPENAI_BASE_URL"):
        raise RuntimeError("规划器缺少模型配置")
    return ChatOpenAI(
        model="qwen3.8-flash", api_key=os.environ["OPENAI_API_KEY"],
        base_url=os.environ["OPENAI_BASE_URL"], temperature=0,
        timeout=25, max_retries=0, max_tokens=1800,
        extra_body={"enable_thinking": False}, use_responses_api=False,
    )  # 初始化客户端；ainvoke时才实际请求供应商。
