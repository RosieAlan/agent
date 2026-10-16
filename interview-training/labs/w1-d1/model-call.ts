import '../../../chapter-02-工程底座/llm/services/chat/src/load-env.js';
import { createChatModel } from '../../../chapter-02-工程底座/llm/services/chat/src/llm/model.factory.js';
import { REQUIREMENT_EXTRACTION_PROMPT } from './prompts.js';

async function main() {
  const input =
    process.argv[2] ??
    '企业管理员需要批量导入 Excel，最多一万行，错误行可以导出。';

  const model = createChatModel();

  const response = await model.invoke([
    {
      role: 'system',
      content: REQUIREMENT_EXTRACTION_PROMPT,
    },
    {
      role: 'user',
      content: input,
    },
  ]);

  console.log(response.text);
}

main().catch((error: unknown) => {
  const status =
    typeof error === 'object' &&
    error !== null &&
    'status' in error
      ? error.status
      : '未提供状态码';

  console.error('模型调用失败，状态码：', status);
  process.exitCode = 1;
});