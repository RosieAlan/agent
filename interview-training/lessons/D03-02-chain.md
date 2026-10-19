# D03第二块：Runnable、pipe与输出解析

2026-10-19。原课程第三章3.6.1–3.6.3，接3.5模板预览。学生已提交prompt-preview.ts离线输出，audience改产品经理后系统消息对应变化，模板填充与独立修改通过。audience在当前模板表示输出受众，系统中的需求抽取助手职责保持；用户选择助手职责需另设计role变量和允许范围。

## 学习目标

必背：Runnable统一调用方式；pipe连接步骤并传递前一步输出；StringOutputParser把模型回复转成文本。会用：追踪变量对象、PromptValue、模型消息和字符串，构建并调用一条链。了解：invoke/stream/batch选型、失败位置、与结构化校验的职责。

## 从分步执行到链

假设prompt、model、parser已经创建，分步阅读片段：

```ts
const promptValue = await prompt.invoke(values);
const response = await model.invoke(promptValue);
const text = await parser.invoke(response);
```

promptValue是填好变量、保留消息结构的提示对象；聊天模型能够接收它。response是AIMessage，含内容及模型元数据；text是解析器返回的字符串。

当这些步骤在需求摘要、接口返回和批处理里重复使用，可以组成一个对象统一调用：

```ts
const chain = prompt.pipe(model).pipe(parser);
const text = await chain.invoke(values);
```

pipe在创建阶段返回组合后的新对象；chain.invoke时执行其中的步骤。前一步输出进入下一步，变量对象→ChatPromptValue→AIMessage→string。各步骤类型需要兼容。

## 新API说明

Runnable是LangChain中可执行组件的共同接口/基类体系，提供invoke、stream、batch等方法。模板、模型和解析器都采用这套约定，调用对象决定实际行为。

pipe是Runnable对象的方法，参数为后续可执行步骤，返回组合后的Runnable。它描述固定顺序；动态分支与循环在后续图编排课程展开。

StringOutputParser来自@langchain/core/output_parsers，new后得到解析器。它接收模型消息或文本，在invoke或链运行到该步时返回字符串。本例处理文本模型回复；JSON语法解析、Schema检查和事实检查继续各司其职。即使字符串形似JSON，返回类型仍为string。

## 学生完整文件

创建interview-training/labs/w1-d3/chain-call.ts，保留已有prompt-preview.ts。下面复用已有依赖和模型工厂，统一模型配置；文件由学生编写/复制。本次invoke含1次真实模型请求，由学生自行运行，教师仅做固定回复的本地框架检查。

```ts
import '../../../chapter-02-工程底座/llm/services/chat/src/load-env.js';
import { createChatModel } from '../../../chapter-02-工程底座/llm/services/chat/src/llm/model.factory.js';
import { ChatPromptTemplate } from '../../../chapter-02-工程底座/llm/services/chat/node_modules/@langchain/core/dist/prompts/index.js';
import { StringOutputParser } from '../../../chapter-02-工程底座/llm/services/chat/node_modules/@langchain/core/dist/output_parsers/index.js';

async function main() {
  const prompt = ChatPromptTemplate.fromMessages([
    ['system', `你是需求分析助手，结果面向{audience}。
依据原文分别给出核心动作、明确约束、待确认事项。`],
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
  console.error('调用失败：', error instanceof Error ? error.name : '未知错误');
  process.exitCode = 1;
});
```

从services/chat运行，模型工厂需要该目录中的config相对路径：

```powershell
cd 'C:\Users\Administrator\Desktop\newAgent\agent-course\chapter-02-工程底座\llm\services\chat'
bun run '../../../../interview-training/labs/w1-d3/chain-call.ts'
```

预期typeof为string，结果描述注册、绑定手机号、密码至少8位，未说明内容为待确认。具体措辞由模型生成。日志只打印本例结果与错误名；敏感配置继续由既有环境配置读取。

## 三种调用方式完整去向

invoke：接收一份values，返回一个最终字符串，适合完整文本结果。

stream：await chain.stream(values)得到可异步迭代的输出，for await消费字符串片段；实际分块能力受模型和组件实现影响。D04完成SSE传给页面、断连和取消处理。

batch：chain.batch([valuesA, valuesB])接收多组变量，正常完成时返回顺序对应的字符串数组。通常是多次模型调用，费用按供应商实际计费；该方法与供应商独立的Batch产品分别理解。部分失败、并发限制、重试在D04展开。

## 失败与标准答案

模板变量缺失在模型调用前失败；模型请求429或超时发生在模型步骤；模型有文本但生成了错误事实时，需要业务检查。chain只负责组合，异常处理、日志和校验仍按步骤设计。

面试：为什么用pipe？答：当模板填充、模型调用、结果解析按固定顺序反复执行时，我把它们组合成一条链，统一传入变量并得到结果，便于复用、替换和检查各步输入输出。

面试：StringOutputParser会把JSON文本变对象并验证字段吗？答：它返回文本字符串；JSON解析负责语法与值转换，Schema负责字段规则，业务逻辑核对事实。结构化输出下一块用withStructuredOutput组合。

作业：运行完整文件，提交结果类型与回复；解释链的输入和最终输出类型。独立修改输入为“管理员可以停用账号，停用后立即禁止登录”，核对结果保留哪些明确条件。无需重复模板预览。独立排错通过已有缺少变量案例与本轮链阶段追踪合并检查。

## 教师证据与来源

固定回复本地检查通过：分步与组合结果一致、结果string、stream片段、batch两项、JSON外观文本保持string、缺少变量失败。供应商请求0次、临时文件0个；学生真实链调用待交。使用本地@langchain/core 1.2.11并查证官方现行API：[pipe](https://reference.langchain.com/javascript/langchain-core/output_parsers/StringOutputParser/pipe)、[StringOutputParser](https://reference.langchain.com/javascript/langchain-core/output_parsers/StringOutputParser)。
