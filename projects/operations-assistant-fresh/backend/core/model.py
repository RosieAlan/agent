import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# 加载当前新项目backend目录中的配置。
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# 创建模型客户端；真正发送请求发生在invoke/ainvoke时。
model = ChatOpenAI(
    model=os.environ["OPENAI_MODEL"],
    api_key=os.environ["OPENAI_API_KEY"],
    base_url=os.environ["OPENAI_BASE_URL"],
    temperature=0,
    timeout=25,           # 单次模型请求超时。
    max_retries=0,        # 当前先关闭自动重试，便于明确观察每次调用。
    use_responses_api=False,  # 当前供应商使用兼容的Chat Completions接口。
)