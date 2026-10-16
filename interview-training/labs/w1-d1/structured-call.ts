import '../../../chapter-02-工程底座/llm/services/chat/src/load-env.js';
import { createChatModel } from '../../../chapter-02-工程底座/llm/services/chat/src/llm/model.factory.js';
import { RequirementSchema } from './schema.js';
import { STRUCTURED_REQUIREMENT_PROMPT } from './prompts.js';

async function main() {
  const input =
    process.argv[2] ??
    '企业管理员需要批量导入 Excel，最多一万行，错误行可以导出。';

  const model = createChatModel();

  const structuredModel =
    model.withStructuredOutput(RequirementSchema);

  const result = await structuredModel.invoke([
    {
      role: 'system',
      content: STRUCTURED_REQUIREMENT_PROMPT,
    },
    {
      role: 'user',
      content: input,
    },
  ]);

  console.log('完整结果：');
  console.log(JSON.stringify(result, null, 2));

  console.log('功能列表：', result.features);
  console.log('待确认事项数量：', result.missingInformation.length);
}

main().catch((error: unknown) => {
  const status =
    typeof error === 'object' &&
    error !== null &&
    'status' in error
      ? error.status
      : '未提供状态码';

  console.error(
    '错误类型：',
    error instanceof Error ? error.name : '未知错误',
  );
  console.error('状态码：', status);

  process.exitCode = 1;
});