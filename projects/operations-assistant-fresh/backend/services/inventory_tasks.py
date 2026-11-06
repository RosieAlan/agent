"""库存任务的启动、读取与恢复；一个任务对应一次用户问题。"""

import asyncio
from contextlib import asynccontextmanager

from services.assistant import build_messages, format_inventory_result


class TaskNotFound(Exception):
    pass


class TaskBusy(Exception):
    pass


class InventoryTasks:
    def __init__(self, graph, pool):
        self.graph = graph
        self.pool = pool
        # 最多两项执行各占一条任务锁连接，池内仍有连接用于写检查点。
        self.slots = asyncio.Semaphore(2)

    @staticmethod
    def config(task_id: str) -> dict:
        return {"configurable": {"thread_id": task_id}, "recursion_limit": 24}

    @asynccontextmanager
    async def task_lock(self, task_id: str):
        """数据库锁跨进程生效，保护同一任务的并发恢复。"""
        async with self.slots:
            async with self.pool.acquire() as connection:
                name = f"ops-task:{task_id}"
                async with connection.cursor() as cursor:
                    await cursor.execute("SELECT GET_LOCK(%s, 0)", (name,))
                    acquired = (await cursor.fetchone())[0] == 1
                if not acquired:
                    raise TaskBusy("该任务正在执行")
                try:
                    yield
                finally:
                    try:
                        async with connection.cursor() as cursor:
                            await cursor.execute("SELECT RELEASE_LOCK(%s)", (name,))
                    except BaseException:
                        connection.close()  # 连接关闭时，MySQL也会释放连接持有的锁。
                        raise

    async def read(self, task_id: str) -> dict:
        state = await self.graph.aget_state(self.config(task_id))
        if not state.created_at:
            raise TaskNotFound("未找到已保存的任务")
        return {
            "task_id": task_id,
            "status": "incomplete" if state.next else "completed",
            "next_nodes": list(state.next),
            "model_rounds": state.values.get("model_rounds", 0),
            "revise_count": state.values.get("revise_count", 0),
            "result": format_inventory_result(state.values) if not state.next else None,
        }  # 只返回业务字段，原始系统消息留在后端。

    async def run(self, task_id: str, input_text: str | None = None) -> dict:
        async with self.task_lock(task_id):
            if input_text is None:  # 恢复：先读取原任务，已完成任务直接返回原结果。
                saved = await self.read(task_id)
                if saved["status"] == "completed":
                    return {"task_id": task_id, **saved["result"]}
                graph_input = None  # LangGraph从保存的待执行节点继续。
            else:
                graph_input = {
                    "messages": build_messages(input_text),
                    "model_rounds": 0,
                    "revise_count": 0,
                }
            result = await self.graph.ainvoke(
                graph_input,
                self.config(task_id),
                durability="sync",  # 每个执行阶段先确认状态落库，再进入下一阶段。
            )
            return {"task_id": task_id, **format_inventory_result(result)}
