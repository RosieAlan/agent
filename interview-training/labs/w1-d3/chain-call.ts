import '../../../chapter-02-工程底座/llm/services/chat/src/load-env.js';
import { createChatModel } from '../../../chapter-02-工程底座/llm/services/chat/src/llm/model.factory.js';
import { ChatPromptTemplate } from '../../../chapter-02-工程底座/llm/services/chat/node_modules/@langchain/core/dist/prompts/index.js';
import { StringOutputParser } from '../../../chapter-02-工程底座/llm/services/chat/node_modules/@langchain/core/dist/output_parsers/index.js';

async function main() {
  const prompt = ChatPromptTemplate.fromMessages([
    [
      'system',
      `你是需求分析助手，结果面向{audience}。
依据原文分别给出核心动作、明确约束、待确认事项。`,
    ],
    ['human', '请整理以下需求：\n{input}'],
  ]);

  const model = createChatModel();
  const parser = new StringOutputParser();

  const chain = prompt.pipe(model).pipe(parser);

  const result = await chain.invoke({
    audience: '产品经理',
    input: '用户注册时必须绑定手机号，密码至少8位。',
  });

  console.log('结果类型：', typeof result);
  console.log('分析结果：\n', result);
}

main().catch(error => {
  console.error(
    '调用失败：',
    error instanceof Error ? error.name : '未知错误',
  );
  process.exitCode = 1;
});