"""库存任务的启动、读取与恢复；一个任务对应一次用户问题。"""

import asyncio
from contextlib import asynccontextmanager

from services.assistant import build_messages, format_inventory_result
from langgraph.types import Command  # 将用户选择交回暂停的图。


class TaskNotFound(Exception):
    pass


class TaskBusy(Exception):
    pass


class TaskConflict(Exception):
    """当前任务状态与本次操作不匹配。"""

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
        # 沿用原任务编号，从检查点读取执行状态。
        state = await self.graph.aget_state(self.config(task_id))

        if not state.created_at:
            raise TaskNotFound("未找到已保存的任务")

        confirmations = []  # 本次找到的待确认事项。

        for task in state.tasks:  # 遍历节点执行记录。
            for pending in task.interrupts:  # 读取该节点产生的暂停信息。
                confirmations.append(
                    {
                        "id": pending.id,  # 这一次暂停的编号。
                        "payload": pending.value,  # interrupt(...)传入的确认内容。
                    }
                )

        if confirmations:
            status = "waiting_confirmation"  # 有暂停信息，等待用户选择。
        elif state.next:
            status = "incomplete"  # 仍有待执行节点。
        else:
            status = "completed"  # 所有节点已执行完毕。

        return {
            "task_id": task_id,
            "status": status,
            "next_nodes": list(state.next),
            "model_rounds": state.values.get("model_rounds", 0),
            "revise_count": state.values.get("revise_count", 0),
            "confirmations": confirmations,
            "result": (
                format_inventory_result(state.values) if status == "completed" else None
            ),  # 流程完成后再整理最终回答。
        }

    async def confirm(self, task_id: str, approved: bool) -> dict:
        """将用户选择交回原任务，然后返回最新状态。"""

        async with self.task_lock(task_id):  # 沿用数据库锁，防止同时恢复同一任务。
            saved = await self.read(task_id)  # 从检查点读取原任务。

            if saved["status"] == "completed":
                return saved  # 重复点击时返回已经保存的结果。

            if saved["status"] != "waiting_confirmation":
                raise TaskConflict("当前任务没有等待用户确认")

            confirmations = saved["confirmations"]

            if len(confirmations) != 1:
                raise TaskConflict("当前接口只处理一个待确认事项")

            confirmation_id = confirmations[0]["id"]  # 定位具体的暂停点。

            await self.graph.ainvoke(
                Command(
                    resume={confirmation_id: approved},
                ),  # 把True或False交给对应的interrupt()。
                self.config(task_id),  # 使用原thread_id，读取原来的执行状态。
                durability="sync",  # 推进前确认检查点已保存。
            )

            return await self.read(task_id)  # 返回完成或再次等待确认的最新状态。

    async def run(
        self, task_id: str, input_text: str | None = None,
        require_confirmation: bool = False,
    ) -> dict:
        async with self.task_lock(task_id):
            if input_text is None:  # 恢复：先读取原任务，已完成任务直接返回原结果。
                saved = await self.read(task_id)
                if saved["status"] == "completed":
                    return {"task_id": task_id, **saved["result"]}
                if saved["status"] == "waiting_confirmation":
                    return saved  # 普通恢复保持等待，选择通过confirm接口提交。
                graph_input = None  # LangGraph从保存的待执行节点继续。
            else:
                graph_input = {
                    "messages": build_messages(input_text),
                    "model_rounds": 0,
                    "revise_count": 0,
                    "require_confirmation": require_confirmation,
                }
            await self.graph.ainvoke(
                graph_input,
                self.config(task_id),
                durability="sync",  # 每个执行阶段先确认状态落库，再进入下一阶段。
            )
            saved = await self.read(task_id)
            if saved["status"] != "completed":
                return saved  # 暂停时返回确认信息，最终答复在任务完成后整理。
            return {"task_id": task_id, **saved["result"]}
