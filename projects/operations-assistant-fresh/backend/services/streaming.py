"""将库存图执行过程整理为浏览器可用的事件。"""

import asyncio
import logging
from contextlib import aclosing

from services.assistant import build_messages
from services.inventory_tasks import InventoryTasks

logger = logging.getLogger(__name__)


async def stream_inventory(
    tasks: InventoryTasks,  # 沿用应用启动时创建的任务服务。
    task_id: str,           # 本次任务编号。
    input_text: str,        # 用户输入。
    require_confirmation: bool = False,  # 与普通接口共用确认开关。
):
    yield {"type": "start", "task_id": task_id}  # 先把编号交给浏览器。

    labels = {
        "confirmation": "执行前确认完成",
        "cancelled": "请求已取消",
        "classifier": "请求分类完成",
        "chat": "回复生成完成",
        "agent": "模型步骤完成",
        "tools": "库存查询完成",
        "critic": "回答检查完成",
        "refine": "回答修订完成",
    }

    try:
        async with asyncio.timeout(60):  # 保留整项任务的等待上限。
            async with tasks.task_lock(task_id):  # 沿用已有任务并发保护。
                graph_input = {
                    "messages": build_messages(input_text),
                    "model_rounds": 0,
                    "revise_count": 0,
                    "require_confirmation": require_confirmation,
                }

                # aclosing保证退出或取消时关闭图的事件流。
                async with aclosing(tasks.graph.astream(
                    graph_input,
                    tasks.config(task_id),  # 沿用检查点编号。
                    stream_mode=["updates", "messages"],  # 同时接收步骤与回答片段。
                    subgraphs=True,        # 接收评审子图内部的修订进度和文字。
                    version="v2",          # 事件统一使用type/data结构。
                    durability="sync",     # 沿用MySQL检查点保存。
                )) as updates:
                    async for part in updates:
                        if part["type"] == "updates":
                            for node_name in part["data"]:
                                if node_name in labels:
                                    yield {
                                        "type": "step",
                                        "step": node_name,
                                        "message": labels[node_name],
                                    }  # 状态和工具原始结果保留在后端。
                        elif part["type"] == "messages":
                            message, metadata = part["data"]
                            node_name = metadata.get("langgraph_node")
                            if node_name not in {"agent", "chat", "refine"}:
                                continue  # 分类和评审结构化结果留在后端。
                            text = message.content
                            if isinstance(text, str) and text:
                                yield {
                                    "type": "delta",
                                    "step": node_name,
                                    "message_id": message.id,
                                    "text": text,
                                }  # 前端按消息编号组装草稿，done时更新最终回答。

                saved = await tasks.read(task_id)  # 图结束后读取最终状态。

                if saved["status"] == "completed":
                    yield {
                        "type": "done",
                        "task_id": task_id,
                        "result": saved["result"],
                    }
                else:
                    yield {
                        "type": saved["status"],
                        "task_id": task_id,
                        "confirmations": saved["confirmations"],
                    }

    except TimeoutError:
        yield {
            "type": "error",
            "task_id": task_id,
            "message": "任务超时，可通过任务编号查询已保存进度",
        }
    except Exception:
        logger.exception("库存流式任务失败 task_id=%s", task_id)
        yield {
            "type": "error",
            "task_id": task_id,
            "message": "任务执行失败，请查看后端日志",
        }
