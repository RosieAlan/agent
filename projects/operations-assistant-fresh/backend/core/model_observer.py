"""使用LangChain回调，记录每次聊天模型调用的耗时和供应商用量。"""

import json
import logging
from threading import Lock
import time

from langchain_core.callbacks import BaseCallbackHandler

from core.observability import request_id_context

logger = logging.getLogger("uvicorn.error")


class ModelLogHandler(BaseCallbackHandler):
    run_inline = True  # 轻量回调直接执行，读取本次调用所在的请求上下文。

    def __init__(self, model_name: str):
        self.model_name = model_name
        self._runs = {}  # 用run_id分别保存并发调用的开始时间与请求编号。
        self._lock = Lock()

    def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs):
        params = kwargs.get("invocation_params") or {}
        state = (
            time.monotonic(),
            request_id_context.get(),
            params.get("model") or params.get("model_name") or self.model_name,
        )
        with self._lock:
            self._runs[run_id] = state  # 只保存计量信息。

    def on_llm_end(self, response, *, run_id, **kwargs):
        # ChatOpenAI一次调用的首个生成结果携带该调用的Token统计。
        message = response.generations[0][0].message if response.generations and response.generations[0] else None
        usage = getattr(message, "usage_metadata", None)
        if usage is None:
            raw = (response.llm_output or {}).get("token_usage") or {}
            usage = {
                "input_tokens": raw.get("prompt_tokens"),
                "output_tokens": raw.get("completion_tokens"),
                "total_tokens": raw.get("total_tokens"),
            }
        self._finish(run_id, "completed", usage)

    def on_llm_error(self, error, *, run_id, **kwargs):
        self._finish(run_id, "failed", {}, type(error).__name__)

    def _finish(self, run_id, outcome, usage, error_type=None):
        with self._lock:
            state = self._runs.pop(run_id, None)  # 结束后释放本次调用的计量状态。
        if state is None:
            return
        started, request_id, model_name = state
        record = {
            "event": "model_call_finished",
            "request_id": request_id,
            "model_run_id": str(run_id),  # 同一HTTP请求可能调用多次模型。
            "model": model_name,
            "outcome": outcome,
            "duration_ms": round((time.monotonic() - started) * 1000, 2),
            "input_tokens": usage.get("input_tokens"),
            "output_tokens": usage.get("output_tokens"),
            "total_tokens": usage.get("total_tokens"),  # 缺少供应商统计时记录null。
        }
        if error_type:
            record["error_type"] = error_type
        logger.info(json.dumps(record))
