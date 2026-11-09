import asyncio
import logging

from app.repositories.conversation_repository import start_turn, finish_turn
from app.services.llm_service import run_ad_tool  # 复用已有Agent。

logger = logging.getLogger(__name__)


async def record_failure(user_id, conversation_id, task_id):
    try:
        await asyncio.shield(
            asyncio.to_thread(
                finish_turn,
                user_id,
                conversation_id,
                task_id,
                None,
            )
        )  # 尝试保存失败事件并清除忙碌状态。
    except Exception:
        logger.exception(
            "task failure persistence failed task_id=%s",
            task_id,
        )  # 数据库故障时，保留可排查的任务编号。


async def chat_in_conversation(
    user_id: str,
    conversation_id: str,
    input_text: str,
) -> dict:
    starting = asyncio.create_task(
        asyncio.to_thread(
            start_turn,
            user_id,
            conversation_id,
            input_text,
        )
    )  # 在线程执行同步数据库操作，保存任务对象供取消时清理。

    try:
        task_id, history = await asyncio.shield(starting)
    except asyncio.CancelledError:
        try:
            task_id, _ = await starting  # 等短事务结束，取得任务编号。
        except Exception:
            logger.exception("cancelled conversation start failed")
        else:
            await record_failure(user_id, conversation_id, task_id)

        raise  # 完成清理后，继续传递取消结果。

    try:
        result = await run_ad_tool(
            input_text,
            history=history,
        )  # 此时start_turn已经归还数据库连接。

        await asyncio.to_thread(
            finish_turn,
            user_id,
            conversation_id,
            task_id,
            result,
        )  # 保存回答和执行结果。

    except (Exception, asyncio.CancelledError):
        await record_failure(user_id, conversation_id, task_id)
        raise  # 错误交给HTTP入口处理。

    return {
        "conversation_id": conversation_id,
        "task_id": task_id,
        **result,
    }