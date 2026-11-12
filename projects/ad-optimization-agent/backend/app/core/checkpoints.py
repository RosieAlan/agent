"""MySQL检查点；运行时只读写已初始化的检查点表。"""

from contextlib import contextmanager
from threading import BoundedSemaphore

from langgraph.checkpoint.mysql.pymysql import PyMySQLSaver

from app.db.business import business_engine

slots = BoundedSemaphore(3)  # 每进程同时最多3个检查点连接，暂停响应后立即关闭连接。


class WorkflowConflict(Exception):
    pass


class MySQLCheckpointSaver(PyMySQLSaver):
    @staticmethod
    def _select_sql(where: str) -> str:
        # 社区包3.0.0的JSON_TABLE联表显式使用一致排序规则，兼容本机MySQL8。
        return PyMySQLSaver._select_sql(where).replace(
            "bl.channel = channel_versions.channel",
            "bl.channel COLLATE utf8mb4_bin = channel_versions.channel COLLATE utf8mb4_bin",
        ).replace(
            "bl.version = channel_versions.version",
            "bl.version COLLATE utf8mb4_bin = channel_versions.version COLLATE utf8mb4_bin",
        )


@contextmanager
def checkpoint_session(thread_id: str):
    if not slots.acquire(timeout=3):
        raise RuntimeError("图状态连接繁忙")
    try:
        uri = business_engine().url.set(drivername="mysql").render_as_string(hide_password=False)
        with MySQLCheckpointSaver.from_conn_string(uri) as saver:
            # 数据库连接级锁跨进程生效，确保同一任务同时只有一个调用方推进状态。
            lock_name = f"adflow:{thread_id}"
            with saver.conn.cursor() as cursor:
                cursor.execute("SELECT GET_LOCK(%s,0)", (lock_name,))
                if cursor.fetchone()[0] != 1:
                    raise WorkflowConflict("该任务正在处理，请稍后刷新")
            try:
                yield saver
            finally:
                with saver.conn.cursor() as cursor:
                    cursor.execute("SELECT RELEASE_LOCK(%s)", (lock_name,))
    finally:
        slots.release()
