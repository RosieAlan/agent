# D02 第三讲：按会话管理聊天历史

2026-10-19。对应原课程第四章4.2.1。当前先读懂历史容器和读写，随后继续同一主题中的RunnableWithMessageHistory自动读写与提示词历史位置。裁剪在第四主题展开。

## 前一题反馈

学生回答“标记为待确认，等待用户说是否永久保存”，事实来源补答通过。当前字段更新与原始历史保留、时间裁剪与重要性的区别保留复习，D02整单元仍在进行。

## 本讲目标

能解释同一会话如何读回原有消息，不同会话如何分开；知道读取、追加、清空分别改变了什么；理解进程内存与数据库保存的区别。API根据本地安装的@langchain/core 1.2.11类型定义核对，以下为原课程机制的阅读片段，尚未单独运行。

## 历史容器

InMemoryChatMessageHistory来自@langchain/core/chat_history，负责在当前后端进程的内存中保存消息并提供读取、追加和清空方法。每个实例可以保存一段对话。

```ts
import { InMemoryChatMessageHistory } from '@langchain/core/chat_history';

const store = new Map<string, InMemoryChatMessageHistory>();

function getHistory(sessionId: string) {
  let history = store.get(sessionId);
  if (!history) {
    history = new InMemoryChatMessageHistory();
    store.set(sessionId, history);
  }
  return history;
}
```

Map按键保存值。键是sessionId字符串，值是该会话对应的历史对象。string和InMemoryChatMessageHistory这两个类型标注约束键和值。

getHistory是本例自己写的函数；参数sessionId指定会话，返回该会话的历史对象。store.get读取已有对象；首次查不到时new创建空对象，store.set登记后返回。store应由服务长期持有，同一服务实例的后续请求才能读回先前记录。

## 调用历史对象的方法

```ts
const historyA = getHistory('a');
await historyA.addUserMessage('我们要做一个需求分析助手。');
await historyA.addAIMessage('已记录，目标用户待确认。');

const messagesA = await historyA.getMessages(); // 2条
const messagesB = await getHistory('b').getMessages(); // 0条

await historyA.clear();
const clearedA = await historyA.getMessages(); // 0条
```

以上文字是已存在问答的教学样本，这些方法只操作历史记录。真实聊天时保存用户输入及实际模型返回的消息。

| 方法 | 参数 | 返回结果/效果 |
|---|---|---|
| addUserMessage | 用户文字 | 追加一条用户消息；await等待完成 |
| addAIMessage | 助手文字 | 追加一条助手消息；await等待完成 |
| getMessages | 无 | 返回已保存的消息对象数组 |
| clear | 无 | 清空这个历史对象的消息；await等待完成 |

这些方法属于历史对象。调用getHistory('a')拿到对象后，才能在对象上调用getMessages等方法。a与b分别映射到不同历史对象，清空a只影响a。读取历史后，仍需将消息放入模型请求，下一步自动历史组件会组织这一过程。

## 工程边界

store放在每次请求内并重新创建，会让每次请求从空记录开始。这个Map应按服务实例保存；服务重启后，进程内历史通常丢失。跨重启保存、多个服务实例共享历史等需求由数据库等持久化方案处理，具体表与查询在数据库单元学习。

按sessionId分开历史提供会话分组。对外接口还要使用可信登录身份校验会话归属，再读取相应历史。当前片段聚焦历史管理，业务权限需接入后端入口。

## 必背与检查

问：内存聊天历史与数据库历史有什么区别？

答：内存历史保存在当前后端进程里，适合演示与临时状态；进程重启或切换实例会影响可读取的记录。数据库历史用于跨重启保存和多实例共享，读取时仍要校验用户及会话归属，再组装模型输入。

检查：a保存一组用户问答，b为空。读取a、清空a、再次读取a和b，消息数分别是什么？

答案：首次读取a为2，清空后a为0，b始终为0。只读操作保持原历史；追加增加消息；clear清空指定对象。

当前口述练习：store放在每次聊天请求函数里面，每次调用都new Map，会导致什么问题？标准答案：每次都得到空存储，前一次保存的历史无法从新Map中读取；应让历史存储由服务长期持有，或接入持久化存储。

## 下一步

继续第三主题：原课程自动历史组件如何读取历史、放进提示词、执行模型并保存本轮问答。学生尚未提交本讲独立解释；完整通过仍为1/32，课程独立总分待测。

## 生命周期补答与自动历史管理

学生已正确补答：Map在函数外由同一进程持有时，下一轮可以读到第一轮消息。该例生命周期检查通过；数据库用于跨重启保存与多实例共享。主动清空也会改变记录，切换进程会读到各自的内存，后续数据库单元继续处理。

### 每个组件先说明用途

- ChatPromptTemplate来自@langchain/core/prompts，它把消息格式定义成模板。fromMessages接收按顺序排列的角色/内容及历史位置，返回模板对象。
- MessagesPlaceholder也来自@langchain/core/prompts。new MessagesPlaceholder('history')在模板中标出插入消息数组的位置，history是本例字段名。
- prompt.pipe(model)返回一条可调用的执行链：先根据输入生成消息，再把消息交给模型。Runnable是这种可调用执行单元的框架名称。
- RunnableWithMessageHistory来自@langchain/core/runnables，接收执行链、历史读取函数及字段名，返回可invoke的对象；调用时读取当前会话历史，送入执行链，成功后追加本轮用户消息和模型回复。

### 阅读片段

以下复用上一节getHistory和D01已配置的model，仅展示自动历史部分；当前无需新建文件或运行。全流程使用无工具、无裁剪的普通聊天链，消息数量按一次成功调用追加一条用户和一条助手消息计算。

```ts
import {
  ChatPromptTemplate,
  MessagesPlaceholder,
} from '@langchain/core/prompts';
import { RunnableWithMessageHistory } from '@langchain/core/runnables';

const prompt = ChatPromptTemplate.fromMessages([
  ['system', '根据对话整理当前需求，缺失条件标为待确认。'],
  new MessagesPlaceholder('history'),
  ['human', '{input}'],
]);

const chain = prompt.pipe(model);

const withHistory = new RunnableWithMessageHistory({
  runnable: chain,
  getMessageHistory: getHistory,
  inputMessagesKey: 'input',
  historyMessagesKey: 'history',
});

const response = await withHistory.invoke(
  { input: '需求单号是REQ-2026-001。' },
  { configurable: { sessionId: 'a' } },
);
```

human是模板中的用户角色写法；{input}是待填入的本轮文字，实际调用时由input字段填充。MessagesPlaceholder把历史数组展开为多条消息，保留各自角色。

四个配置：runnable指定真正执行任务的chain；getMessageHistory提供函数供组件按会话编号查找历史，这里传函数本身；inputMessagesKey指定新消息取自input字段；historyMessagesKey指定读取的历史放入history字段。

invoke的第一个参数是业务输入；第二个参数是运行配置。configurable.sessionId选定a会话；本次response返回链输出的模型消息。input/history字段名要分别与模板和组件配置对应。

### 完整执行顺序

假设a已存两条第一轮问答，b为空：

1. 组件从配置取sessionId='a'，调用getHistory('a')并读取两条消息。
2. 将历史放到history字段，本轮文字来自input字段。
3. prompt生成system规则、旧user、旧assistant、新user，共4条模型输入消息。
4. chain调用model，拿到新assistant消息。
5. 成功后组件向a追加本轮用户消息和模型回复，a的已保存历史变为4条；b保持空。

此例system由模板每轮生成，保存的会话历史为用户与助手消息。自动组件已经负责本轮保存时，调用方应保持单一保存责任，避免再手工追加同一轮导致重复。本例getHistory只读当前容器并在缺失时创建，不额外写入本轮消息。

### 字段错误排查及必背答案

historyMessagesKey写成history而模板占位写成oldMessages，会发生字段不匹配。检查模板占位名、组件历史字段名，以及本轮input字段名、会话配置是否逐一对应。

问：自动历史管理实际自动做了什么？

答：它根据会话编号找到历史，读取旧消息，把旧消息交给提示模板，与本轮输入共同发送给模型；成功后把本轮用户消息和模型回复追加到同一会话。存储位置由历史实现决定，当前例子保存在内存里。

检查：a原有2条问答历史，本轮模型输入含几条消息，成功后a存几条？

答案：本例输入4条，包含system、两条历史和本轮user；成功后历史4条，包含两轮各一条user与assistant。system由模板提供。

### 版本说明与状态

本地@langchain/core 1.2.11的类型定义已把RunnableWithMessageHistory标注deprecated，并推荐LangGraph持久化。保留原课程这一节，完整理解和读懂已有代码；LangGraph的状态与持久化按D09/D10继续学习。当前阅读片段已核对原文和本地API声明，尚未单独执行，学生新一轮理解待检查。
