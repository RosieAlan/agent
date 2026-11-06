"""在backend目录运行：python -m scripts.init_checkpoints。"""

import asyncio

from core.checkpoints import checkpoint_resources


async def main():
    async with checkpoint_resources() as (_, saver):
        await saver.setup()  # 首次建表；升级依赖时按发布流程执行迁移。
        print("MySQL检查点表初始化完成")


if __name__ == "__main__":
    asyncio.run(main())
