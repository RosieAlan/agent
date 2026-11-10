"""请求关联与步骤耗时；日志输出交给现有Uvicorn配置。"""

from contextlib import contextmanager
from contextvars import ContextVar
import json
import logging
import time

logger = logging.getLogger("uvicorn.error")
request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)


@contextmanager
def log_step(name: str):
    """测量with代码块的耗时，记录请求编号、结果和异常类型。"""
    started = time.monotonic()  # 单调时钟用于计算时长，避免系统校时影响。
    outcome = "completed"
    error_type = None
    try:
        yield  # 执行调用方with缩进里的代码。
    except BaseException as error:
        outcome = "failed"
        error_type = type(error).__name__  # 只记类型，错误处理继续交给原调用链。
        raise
    finally:
        record = {
            "event": "step_finished",
            "request_id": request_id_context.get(),  # 读取当前请求自己的编号。
            "step": name,
            "outcome": outcome,
            "duration_ms": round((time.monotonic() - started) * 1000, 2),
        }
        if error_type:
            record["error_type"] = error_type
        logger.info(json.dumps(record))  # 每条日志输出一个JSON对象。
