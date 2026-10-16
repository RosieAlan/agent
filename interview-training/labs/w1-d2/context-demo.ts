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
      content: [
        '你是需求分析助手。综合本次提供的全部消息，',
        '输出需求摘要、已知约束、待确认事项。',
        '事实须有消息依据，缺失信息标为待确认。',
        '用户明确修改条件时，采用最新条件。',
      ].join(''),
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