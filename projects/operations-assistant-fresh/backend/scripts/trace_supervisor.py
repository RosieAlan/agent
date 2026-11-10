"""检查Langfuse连接，或生成一条可在页面查看的专家选择记录。"""

import argparse
import asyncio

from services.supervisor import select_experts  # 同时加载当前项目.env和模型配置。
from core.tracing import tracing_client


async def main():
    parser = argparse.ArgumentParser(description="连接Langfuse并观察专家选择")
    parser.add_argument("--check", action="store_true", help="只检查Langfuse认证")
    parser.add_argument("--input", default="查询OPS-EARBUDS-001的库存。")
    args = parser.parse_args()
    client = tracing_client()
    if client is None:
        raise SystemExit("请在.env配置Langfuse项目并设置LANGFUSE_ENABLED=true")
    try:
        if not client.auth_check():  # 检查地址和项目凭据；此操作无需调用模型。
            raise SystemExit("Langfuse认证未通过，请核对项目地址和密钥")
        print("Langfuse连接成功")
        if args.check:
            return
        with client.start_as_current_observation(
            as_type="span",
            name="inventory-routing-demo",
            input={"input": args.input},  # 记录合成样例任务，供页面查看。
        ) as span:
            result = await select_experts(args.input)  # 真实调用当前配置的Flash模型。
            span.update(output=result.model_dump())  # 给最外层记录补上最终结果。
            url = client.get_trace_url()  # 获取本次记录的页面链接。
        print(result.model_dump_json(indent=2))
        print("打开本次Trace：", url)
    finally:
        client.shutdown()  # 短脚本结束前发送待上报事件并释放后台资源。


if __name__ == "__main__":
    asyncio.run(main())
