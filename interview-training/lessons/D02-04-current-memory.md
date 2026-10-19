# D02 第三主题现行方案：会话状态、检查点与会话编号

2026-10-19。覆盖原课程第四章4.2.1的会话延续/读写目标；替代此前已弃用的历史包装组件。当前为D02第三主题的继续，D09/D10完整学习图编排和数据库检查点。

## 目标与名词

必背：state保存当前会话数据，checkpointer负责保存和恢复状态，thread_id用来选定会话。会话延续需要使用同一份检查点存储与同一个thread_id；数据库实现提供跨重启保存。

state是框架提供给执行过程的数据对象。本例关心其中messages数组，它保留该会话用户消息与模型回复。

checkpointer是保存/读取状态快照的组件。快照就是执行到某一步时的数据记录。MemorySaver是LangGraph提供的内存实现；它在当前进程中保存这些记录。PostgresSaver等数据库实现用于跨重启保存，后续专门接入。

thread_id是运行配置中的会话标识。同一个值选择同一会话历史，不同值分别记录。可信登录用户与会话归属仍由后端入口校验。

createAgent来自langchain，创建基于LangGraph运行的执行对象；本课传入模型、系统要求、空工具列表和checkpointer。tools: []表示本例只进行模型对话；工具执行在D06完整学习。

## 阅读片段

以下复用D01已配置的model。State在此由createAgent管理，消息的追加与检查点读写由框架完成。

```ts
import { createAgent } from 'langchain';
import { MemorySaver } from '@langchain/langgraph';

const checkpointer = new MemorySaver();

const agent = createAgent({
  model,
  tools: [],
  systemPrompt: '根据已有对话回答，未知条件明确说明。',
  checkpointer,
});

const configA = { configurable: { thread_id: 'a' } };

await agent.invoke(
  { messages: [{ role: 'user', content: '需求单号是REQ-2026-001。' }] },
  configA,
);

const result = await agent.invoke(
  { messages: [{ role: 'user', content: '刚才的需求单号是什么？' }] },
  configA,
);
```

MemorySaver创建时无参数，得到保存状态的对象。createAgent接收配置后返回agent，可调用invoke。model提供模型对象；systemPrompt提供本例每轮使用的规则；checkpointer启用会话状态保存。

invoke第一个参数提供本轮新增消息，第二个参数提供运行配置。第二轮同一会话由框架恢复之前状态，再合并新增消息，因此调用方传入本轮新消息即可。调用方重复传回整段已保存历史会增加重复合并风险，需要明确消息ID和更新规则；本例保持单一历史管理责任。

两轮成功后普通无工具会话messages为4条：第一轮user/assistant、第二轮user/assistant。systemPrompt用于模型请求，本例保存在状态中的messages只计用户与助手消息。

## 逐轮过程

第一轮：thread_id=a → 读取a已有状态（首次为空）→ 加入本轮user → 模型得到规则和该消息 → 回复写入messages → 保存a检查点。

第二轮：thread_id=a → 恢复a的两条消息 → 加入本轮user → 模型拿到规则、历史及本轮消息 → 回复写入messages → 保存更新后的a检查点。

另一次调用选择thread_id=b：首次读取b为空，a的记录继续属于a，b本轮输入缺少a的需求编号。存储长期持有与会话编号稳定都需要保证。

## 完整学生练习文件

学生自行创建 interview-training/labs/w1-d2/memory-current.ts。以下路径复用现有项目模型配置及依赖；直接文件路径导入用于仓库外置labs访问已有依赖，正式项目源码通常使用包名导入。当前文件是完整练习内容，教师尚未创建业务文件。

```ts
import '../../../chapter-02-工程底座/llm/services/chat/src/load-env.js';
import { createChatModel } from '../../../chapter-02-工程底座/llm/services/chat/src/llm/model.factory.js';
import { createAgent } from '../../../chapter-02-工程底座/llm/services/chat/node_modules/langchain/dist/index.js';
import { MemorySaver } from '../../../chapter-02-工程底座/llm/services/chat/node_modules/@langchain/langgraph/dist/index.js';

async function main() {
  const model = createChatModel();
  const checkpointer = new MemorySaver();
  const agent = createAgent({
    model,
    tools: [],
    systemPrompt: '根据当前会话提供的信息回答。需求单号未知时明确说未知。简短回答。',
    checkpointer,
  });

  const configA = { configurable: { thread_id: 'a' } };
  const configB = { configurable: { thread_id: 'b' } };

  const first = await agent.invoke(
    { messages: [{ role: 'user', content: '需求单号是REQ-2026-001，我们要做一个需求分析助手。' }] },
    configA,
  );
  console.log('A第一轮：', first.messages.at(-1)?.content);

  const second = await agent.invoke(
    { messages: [{ role: 'user', content: '刚才的需求单号是什么？' }] },
    configA,
  );
  console.log('A第二轮：', second.messages.at(-1)?.content);

  const other = await agent.invoke(
    { messages: [{ role: 'user', content: '当前会话的需求单号是什么？' }] },
    configB,
  );
  console.log('B第一轮：', other.messages.at(-1)?.content);

  const savedA = await agent.getState(configA);
  const savedB = await agent.getState(configB);
  console.log('A历史条数：', savedA.values.messages.length);
  console.log('B历史条数：', savedB.values.messages.length);
}

main().catch((error: unknown) => {
  console.error('运行失败：', error instanceof Error ? error.name : '未知错误');
  process.exitCode = 1;
});
```

getState(config)读取该会话保存的状态快照；返回对象的values是会话数据，values.messages是消息数组。messages.at(-1)取最后一条消息，?.content取它的内容，存在消息时用于展示助手回复。当前代码直接读框架状态，数据库业务表与检查点的对应关系后续单元继续讲。

运行位置为 chapter-02-工程底座/llm/services/chat，命令：

```powershell
bun run ../../../../interview-training/labs/w1-d2/memory-current.ts
```

这次完整运行包含3次真实模型请求。预期A第二轮能引用REQ-2026-001；B应说明本会话缺少需求编号；A保存4条、B保存2条。回复是待学生验证的模型行为；消息隔离同时检查实际状态，单看回复文本无法充分证明隔离。

## 本地验证与学生验收分别记录

教师使用项目安装版本langchain 1.5.11、langgraph 1.4.15与固定回复模型，在内存中验证同样的createAgent/MemorySaver/invoke/getState流程：返回消息数2/4/2，最终保存A=4、B=2，B状态没有A的需求编号。该验证覆盖实际框架API与状态隔离，固定回复无需供应商请求；真实模型、真实配置与学生独立理解待提交。

本轮练习未创建临时文件，既有学生trim-demo.ts保留。未来数据库checkpointer仍要额外验证重启恢复；MemorySaver本例继续按进程内保存解释。

## 必背、排错与独立修改

问：LangGraph怎样实现多轮会话？

答：用thread_id选择会话，用checkpointer读取和保存该会话状态。每轮传入新消息，框架恢复旧状态并合并新消息，将相关消息交给模型，再把回复写回状态。状态保存在内存还是数据库，由checkpointer实现决定。

检查题：第二轮thread_id从a改为b，会怎样？

答案：读取b的状态；b首次为空时，模型输入缺少a的历史。a的原记录仍留在检查点存储中。

独立修改：完成原例后，先预测将第二轮配置改为configB会发生什么，说明应恢复哪个会话的记录；按需要合并到正式综合验收，避免无目的重复付费请求。

排错：同一会话接不上时，检查thread_id是否稳定、checkpointer是否长期持有、状态是否读回，以及模型节点是否获得所需messages。请求报错先确认上游配置，状态存在但答错继续核对模型实际输入与事实依据。

## 原文与官方来源

- 原课程第四章4.2.1：读取历史、加入输入、保存问答、会话隔离，均映射至本讲。
- [LangChain短期记忆与createAgent](https://docs.langchain.com/oss/javascript/langchain/short-term-memory)
- [LangGraph会话记忆](https://docs.langchain.com/oss/javascript/langgraph/add-memory)
- [检查点存储与持久化](https://docs.langchain.com/oss/javascript/langgraph/persistence)

进度：D02第三主题现行方案授课/练习，学生运行待交；第四主题预算/裁剪待完整授课。整体通过1/32，课程独立总分待测。

## 学生真实运行及checkpointer补讲（10月19日）

学生已创建练习并提交结果：A第一轮记录需求号REQ-2026-001；A第二轮回答REQ-2026-001；B第一轮回答未知；A历史4条，B历史2条。本例真实模型会话延续与消息数符合预期，跨会话回答符合隔离预期。此记录依据学生提供的终端输出，教师没有另行发起付费模型请求。

学生追问checkpointer是什么。直接答案：checkpointer是负责保存和读回会话状态的组件；本例由MemorySaver完成这项工作。const checkpointer = new MemorySaver()创建这个对象，createAgent配置中的checkpointer把对象交给框架使用。A第一轮执行时保存状态，A第二轮根据thread_id=a读回原状态后继续，b选择自己的状态记录。存储实现决定数据保存在内存还是数据库，MemorySaver仍随进程生命周期，跨重启保存使用数据库实现。

必背：thread_id决定找哪段会话；checkpointer负责保存和恢复这段会话的状态；本例的MemorySaver把状态保存在当前进程内存中。

当前运行已通过，checkpointer独立解释待答；整体仍为1/32，第四主题预算与裁剪待学。
