import '../../../chapter-02-工程底座/llm/services/chat/src/load-env.js';
import { createChatModel } from '../../../chapter-02-工程底座/llm/services/chat/src/llm/model.factory.js';
import {
  ChatPromptTemplate,
  MessagesPlaceholder,
} from '../../../chapter-02-工程底座/llm/services/chat/node_modules/@langchain/core/prompts.js';
import {
  RunnableWithMessageHistory,
} from '../../../chapter-02-工程底座/llm/services/chat/node_modules/@langchain/core/runnables.js';
import {
  InMemoryChatMessageHistory,
} from '../../../chapter-02-工程底座/llm/services/chat/node_modules/@langchain/core/chat_history.js';

const store = new Map<string, InMemoryChatMessageHistory>();

function getHistory(sessionId: string) {
  let history = store.get(sessionId);

  if (!history) {
    history = new InMemoryChatMessageHistory();
    store.set(sessionId, history);
  }

  return history;
}

async function main() {
  const model = createChatModel();

  const prompt = ChatPromptTemplate.fromMessages([
    ['system', [
      '你是需求分析助手，根据用户消息整理需求。',
      '输出需求摘要、已知约束、待确认事项。',
      '用户明确修改条件时采用最新条件，保留其他已确认内容。',
      '缺失信息标为待确认，本轮最多问3个关键问题。',
    ].join('\n')],

    new MessagesPlaceholder('history'),

    ['human', '{input}'],
  ]);

  const chain = prompt
    .pipe((value) => {
      console.log('本次发给模型的消息：', value.toChatMessages());
      return value;
    })
    .pipe(model);

  const withHistory = new RunnableWithMessageHistory({
    runnable: chain,
    getMessageHistory: getHistory,
    inputMessagesKey: 'input',
    historyMessagesKey: 'history',
  });

  async function chat(sessionId: string, input: string) {
    const response = await withHistory.invoke(
      { input },
      { configurable: { sessionId } },
    );

    console.log('模型回复：', response.text);
  }

  await chat('demo-a', '企业管理员需要批量导入Excel，最多一万行。');

  console.log('第一轮后demo-a记录数：',
    (await getHistory('demo-a').getMessages()).length);
  await getHistory('demo-a').clear();
  await chat('demo-a',
    '改成最多五千行，错误行需要导出，其他要求保持不变。');

  console.log('第二轮后demo-a记录数：',
    (await getHistory('demo-a').getMessages()).length);

  console.log('demo-b记录数：',
    (await getHistory('demo-b').getMessages()).length);

  await getHistory('demo-a').clear();

  console.log('清空后demo-a记录数：',
    (await getHistory('demo-a').getMessages()).length);

  // 固定样本：演示手动补入一组已有问答。
  await getHistory('demo-a').addUserMessage('需要导入Excel。');
  await getHistory('demo-a').addAIMessage('已记录，导入规则待确认。');

  console.log('手动补入后demo-a记录数：',
    (await getHistory('demo-a').getMessages()).length);
}

main().catch((error: unknown) => {
  console.error('调用失败，错误类型：',
    error instanceof Error ? error.name : '未知错误');

  process.exitCode = 1;
});