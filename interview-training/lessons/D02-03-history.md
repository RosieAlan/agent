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
