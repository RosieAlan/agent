"""教学客户端：通过独立子进程发现并调用库存 MCP 工具。"""

import argparse
import asyncio
import json
from pathlib import Path
import sys

from mcp import Client, StdioServerParameters


async def main() -> int:
    parser = argparse.ArgumentParser(description="发现并调用库存MCP工具")
    parser.add_argument("--sku", default="OPS-EARBUDS-001")
    parser.add_argument("--threshold", type=int, default=20)
    args = parser.parse_args()
    backend_dir = Path(__file__).resolve().parents[1]  # 定位当前项目backend目录。
    server = StdioServerParameters(
        command=sys.executable,  # 使用当前项目虚拟环境里的Python。
        args=["-X", "utf8", str(backend_dir / "inventory_mcp_server.py")],
        cwd=str(backend_dir),  # 固定工作目录，避免从其他位置启动时导入失败。
    )

    async with Client(server, read_timeout_seconds=20) as client:
        # 进入async with时启动子进程并连接；退出时关闭连接及子进程。
        listed = await client.list_tools()  # 向Server获取工具清单。
        print("可用工具：", [tool.name for tool in listed.tools])
        result = await client.call_tool(
            "check_inventory",  # 对应服务端注册的函数名。
            {"sku": args.sku, "threshold": args.threshold},  # 本次工具参数。
        )
        if result.is_error:  # MCP返回的工具执行失败标记。
            print("工具失败：", result.content)
            return 1
        print("库存结果：")
        print(json.dumps(result.structured_content, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))  # 运行异步客户端，并向终端返回退出码。
