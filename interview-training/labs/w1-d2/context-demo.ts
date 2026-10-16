import '../../../chapter-02-工程底座/llm/services/chat/src/load-env.js';
import { createChatModel } from '../../../chapter-02-工程底座/llm/services/chat/src/llm/model.factory.js';

async function main() {
  const mode = process.argv[2] ?? 'history';
  const model = createChatModel();

  const history = [
    {
      role: 'user' as const,
      content: '企业管理员需要批量导入 Excel，最多一万行。',
    },
    {
      role: 'assistant' as const,
      content: '已记录需求，行数上限的适用范围待确认。',
    },
  ];

  const messages = [
    {
      role: 'system' as const,
    //   content: [
    //     '你是需求分析助手。综合本次提供的全部消息，',
    //     '输出需求摘要、已知约束、待确认事项。',
    //     '事实须有消息依据，缺失信息标为待确认。',
    //     '用户明确修改条件时，采用最新条件。',
    //   ].join(''),
          content: [
        '你是需求分析助手，请综合本次提供的全部消息。',
        '输出三个部分：需求摘要、已知约束、待确认事项。',
        '需求事实以user消息中的明确表述为依据。',
        '同一需求的同一条件被用户明确修改时，采用最新条件。',
        '其余已确认信息继续保留，缺失或含糊的信息标为待确认。',
        '待确认事项按影响业务决策和验收的程度排序，本轮最多提出3个问题。',
        '优先询问影响数据校验、导入范围和错误处理结果的缺失条件。',
        '每个问题聚焦一个决策，表达简短、具体，已明确的信息直接复用。',
        '建议与推测单独标明，已知约束只写有消息依据的事实。',
      ].join('\n'),
    },
    ...(mode === 'history' ? history : []),
    {
      role: 'user' as const,
     content: '改成最多五千行，错误行需要导出，其他要求保持不变。',
    },
  ];

  console.log('实际发送的消息：', messages);
  const response = await model.invoke(messages);
  console.log('模型回复：', response.text);
}

main().catch((error: unknown) => {
  console.error(
    '调用失败，错误类型：',
    error instanceof Error ? error.name : '未知错误',
  );
  process.exitCode = 1;
});