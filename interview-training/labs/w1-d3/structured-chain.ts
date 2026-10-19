import '../../../chapter-02-工程底座/llm/services/chat/src/load-env.js';
import { createChatModel } from '../../../chapter-02-工程底座/llm/services/chat/src/llm/model.factory.js';
import { ChatPromptTemplate } from '../../../chapter-02-工程底座/llm/services/chat/node_modules/@langchain/core/dist/prompts/index.js';
import { z } from '../../../chapter-02-工程底座/llm/services/chat/node_modules/zod/index.js';

const RequirementResultSchema = z.object({
  action: z.string().describe('原文的核心动作，使用动词加对象概括'),
  constraints: z.array(z.string()).describe('原文明确提出的限制条件'),
  entities: z.array(z.string()).describe('原文涉及的人或事物名称'),
});

type RequirementResult = z.infer<typeof RequirementResultSchema>;

async function main() {
  const input =
    process.argv[2] ?? '用户注册时必须绑定手机号，密码至少8位。';

  const prompt = ChatPromptTemplate.fromMessages([
    [
      'system',
      `你是需求结构化抽取助手，结果面向{audience}。
提取核心动作、明确约束、涉及对象。
事实以用户原文为依据，明确约束只记录原文已经说明的内容。
尚未说明的短信验证码、手机号格式、密码复杂度等保留为未知。
缺少核心动作时action填空字符串；缺少约束或对象时对应数组填空数组。`,
    ],
    ['human', '请整理以下需求：\n{input}'],
  ]);

  const model = createChatModel();

  const structuredModel =
    model.withStructuredOutput(RequirementResultSchema);

  const chain = prompt.pipe(structuredModel);

  const result: RequirementResult = await chain.invoke({
    audience: '产品经理',
    input,
  });

  console.log('完整结果：\n', JSON.stringify(result, null, 2));
  console.log('核心动作：', result.action);
  console.log('约束数量：', result.constraints.length);
  console.log('约束是数组：', Array.isArray(result.constraints));
}

main().catch((error: unknown) => {
  console.error(
    '结构化调用失败：',
    error instanceof Error ? error.name : '未知错误',
  );

  process.exitCode = 1;
});