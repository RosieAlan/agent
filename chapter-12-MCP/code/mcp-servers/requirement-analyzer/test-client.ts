import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';

async function main() {
  const transport = new StdioClientTransport({
    command: 'npx',
    args: ['tsx', 'src/index.ts'],
  });

  const client = new Client({ name: 'test-client', version: '1.0.0' }, { capabilities: {} });

  console.log('▶ 正在连接 Server...');
  await client.connect(transport);
  console.log('✅ 连接成功，能力协商完成\n');

  const { tools } = await client.listTools();
  console.log('▶ Server 暴露的工具列表 (tools/list)：');
  console.log(tools.map((t) => `  - ${t.name}: ${t.description}`).join('\n'));

  console.log('\n▶ 调用 analyze_completeness（用一段不完整的需求测试）...');
  const result = await client.callTool({
    name: 'analyze_completeness',
    arguments: {
      requirementText: '用户希望能够导出报表',
    },
  });

  console.log('✅ 调用结果：');
  console.log(result.content);

  await client.close();
  console.log('\n▶ 连接已关闭');
}

main().catch((err) => {
  console.error('❌ 出错：', err);
  process.exit(1);
});
