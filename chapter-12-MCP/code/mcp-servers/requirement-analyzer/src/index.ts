import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';

const server = new McpServer({
  name: 'requirement-analyzer',
  version: '1.0.0',
});

server.tool(
  'analyze_completeness',
  '分析需求描述的完整性，检查是否缺少关键维度（用户角色、功能描述、验收标准、非功能需求等）',
  {
    requirementText: z.string().describe('需求描述文本'),
  },
  async ({ requirementText }) => {
    const dimensions = [
      { name: '用户角色', keywords: ['用户', '角色', '作为', 'PM', '开发', '管理员', '运营'], found: false },
      { name: '功能描述', keywords: ['能够', '可以', '支持', '实现', '功能', '需要', '希望'], found: false },
      { name: '验收标准', keywords: ['验收', '标准', '条件', '期望', '预期结果', '应该', '必须'], found: false },
      { name: '优先级', keywords: ['优先', 'P0', 'P1', 'P2', '紧急', '重要', '高', '低'], found: false },
      { name: '非功能需求', keywords: ['性能', '安全', '可用性', '并发', '响应时间', '可靠', '稳定'], found: false },
      { name: '边界条件', keywords: ['边界', '异常', '限制', '最大', '最小', '超出', '错误', '失败'], found: false },
    ];

    for (const dim of dimensions) {
      dim.found = dim.keywords.some((kw) => requirementText.includes(kw));
    }

    const missing = dimensions.filter((d) => !d.found).map((d) => d.name);
    const covered = dimensions.filter((d) => d.found).map((d) => d.name);
    const score = Math.round((covered.length / dimensions.length) * 100);

    return {
      content: [
        {
          type: 'text' as const,
          text: JSON.stringify(
            {
              completenessScore: score,
              totalDimensions: dimensions.length,
              coveredDimensions: covered,
              missingDimensions: missing,
              suggestion:
                missing.length > 0
                  ? `建议补充以下维度：${missing.join('、')}`
                  : '需求描述较为完整',
            },
            null,
            2,
          ),
        },
      ],
    };
  },
);

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error('requirement-analyzer MCP Server running on stdio');
}

main().catch((err) => {
  console.error('Fatal error:', err);
  process.exit(1);
});
