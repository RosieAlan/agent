import {
  AIMessage,
  HumanMessage,
  SystemMessage,
  trimMessages,
} from '../../../chapter-02-工程底座/llm/services/chat/node_modules/@langchain/core/messages.js';

async function main() {
  const history = [
    new HumanMessage('企业管理员需要批量导入Excel，最多一万行。'),
    new AIMessage('已记录，行数适用范围待确认。'),
    new HumanMessage('错误行需要导出。'),
    new AIMessage('已记录错误行导出，其他规则待确认。'),
  ];

  const keepCount = Number(process.argv[2] ?? '2');

  if (!Number.isInteger(keepCount) || keepCount < 0) {
    throw new Error('保留条数需要填写0或正整数');
  }

  const trimmer = trimMessages({
    maxTokens: keepCount,
    tokenCounter: (messages) => messages.length,
    strategy: 'last',
    startOn: 'human',
    allowPartial: false,
  });

  const selected = await trimmer.invoke(history);

  console.log('原历史数量：', history.length);
  console.log('本次选中数量：', selected.length);
  console.log('本次选中内容：', selected.map((m) => m.text));

  const system = new SystemMessage([
    '根据用户消息和已确认数据整理需求。',
    '用户明确修改条件时采用最新条件。',
    '缺失信息标为待确认。',
  ].join('\n'));

  const current = new HumanMessage(
    '改成最多五千行，其他要求保持不变。',
  );

  const onlyRecent = [system, ...selected, current];

  console.log('只带最近历史的请求：',
    onlyRecent.map((m) => m.text));

  // 教学固定样本：根据用户原话和最新修改整理。
  const confirmed = {
    targetUser: '企业管理员',
    fileType: 'Excel',
    maxRows: 5000,
    limitScope: '待确认',
    exportErrorRows: true,
  };

  const facts = new HumanMessage(
    `按用户原话整理的当前需求数据：${JSON.stringify(confirmed)}`,
  );

  const withFacts = [system, facts, ...selected, current];

  console.log('补入已确认数据后的请求：',
    withFacts.map((m) => m.text));

  console.log('检查后原历史数量：', history.length);
}

main().catch((error: unknown) => {
  console.error(
    error instanceof Error ? error.message : '未知错误',
  );

  process.exitCode = 1;
});