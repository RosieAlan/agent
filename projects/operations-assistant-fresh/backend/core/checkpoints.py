"""MySQL检查点连接；与业务查询共用数据库，使用独立异步连接池。"""

from contextlib import asynccontextmanager

import aiomysql
from langgraph.checkpoint.mysql.aio import AIOMySQLSaver

from db import database_url


class ProjectMySQLSaver(AIOMySQLSaver):
    """兼容3.0.0读取SQL中JSON_TABLE与MySQL8区分大小写排序规则。"""

    @staticmethod
    def _select_sql(where: str) -> str:
        sql = AIOMySQLSaver._select_sql(where)
        # JSON_TABLE生成的channel采用字符集默认规则，JOIN显式按二进制规则比较。
        return sql.replace(
            "bl.channel = channel_versions.channel",
            "bl.channel COLLATE utf8mb4_bin = channel_versions.channel COLLATE utf8mb4_bin",
        ).replace(
            "bl.version = channel_versions.version",
            "bl.version COLLATE utf8mb4_bin = channel_versions.version COLLATE utf8mb4_bin",
        )


@asynccontextmanager
async def checkpoint_resources():
    """进程启动时创建连接池，退出时归还并关闭连接。"""
    pool = await aiomysql.create_pool(
        host=database_url.host,
        port=database_url.port,
        user=database_url.username,
        password=database_url.password,
        db=database_url.database,
        charset="utf8mb4",
        init_command="SET NAMES utf8mb4 COLLATE utf8mb4_0900_as_cs",  # 与MySQL8检查点表的排序规则保持一致。
        autocommit=True,  # 检查点写入后立即提交。
        minsize=1,
        maxsize=5,
        connect_timeout=5,
        pool_recycle=1800,
    )
    try:
        yield pool, ProjectMySQLSaver(pool)  # saver通过连接池读写图状态。
    finally:
        pool.close()
        await pool.wait_closed()
