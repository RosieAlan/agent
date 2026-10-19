import { ChatPromptTemplate } from '../../../chapter-02-工程底座/llm/services/chat/node_modules/@langchain/core/dist/prompts/index.js';

const REQUIREMENT_SYSTEM_PROMPT = `
你是一名需求结构化抽取助手，结果面向{audience}。
任务：从用户原文提取核心动作、明确约束、涉及对象。
事实以用户原文为依据，缺失内容标为待确认。
`.trim();

const REQUIREMENT_USER_TEMPLATE = `
请整理以下需求：
{input}
`.trim();

const requirementPrompt = ChatPromptTemplate.fromMessages([
  ['system', REQUIREMENT_SYSTEM_PROMPT],
  ['human', REQUIREMENT_USER_TEMPLATE],
]);

const values = {
  audience: '产品经理',
  input: '用户注册时必须绑定手机号，密码至少8位。',
};

const messages = await requirementPrompt.formatMessages(values);

console.log('系统消息：', messages[0].content);
console.log('用户消息：', messages[1].content);

const promptValue = await requirementPrompt.invoke(values);
console.log('完整预览：\n', promptValue.toString());