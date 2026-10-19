# D03第一块：Prompt模板、消息渲染与模型调用位置

2026-10-19，用户明确要求进入D03。D02授课完成，已有主要真实运行证据；两处综合错题保留复习，独立验收尚待收尾。本次推进由用户明确授权，单元通过数按已有证据保持1/32。

## 今日四个完整目标

1. 提示模板：原第三章3.5.1–3.5.5，拆出固定规则和变量，预览消息，再接模型。
2. 调用链：原3.6.1–3.6.3，解释Runnable、pipe和StringOutputParser，逐步追踪类型与数据。
3. 结构化接口：原3.7及工程底座对应部分，把模板、结构化模型和服务端接口组合，验证正常与失败分支。
4. 独立修改与排错：字段变更、缺少变量、结构正确但事实错误，完整串联D01–D03并核对章节清单。

本讲完整覆盖第一目标。后续重要内容继续在本D单元逐块完成，授课和实操状态分开。

## 为什么要有模板

同一需求抽取功能可以从聊天页、后台或批处理入口使用。固定的任务规则集中保存，每次把用户输入和受众等变化值传入，可减少规则散落。变量填充、消息角色和模型生成分步排查。

类比熟悉的JS函数：模板相当于可复用的文字结构，调用时传入参数。模板中的{input}表示等待填充的位置；JS的${input}在模板字符串求值时插入，LangChain占位符在formatMessages或invoke时按传入对象填充。

## 新API先解释

ChatPromptTemplate来自@langchain/core/prompts，用于描述聊天模型的多条消息模板。

- fromMessages接收角色与文本组成的数组，创建模板对象。['system',文本]表示系统要求；['human',文本]生成用户消息。创建模板时保留占位符。
- formatMessages接收变量对象，返回Promise<BaseMessage[]>；await后得到已填好内容的消息数组，可交给model.invoke。
- prompt.invoke接收变量对象，返回ChatPromptValue；toString用于查看带角色的预览，toChatMessages可取得消息数组。
- model.invoke接收模型输入，调用供应商并返回模型消息。对象不同，invoke执行的操作不同。

## 原课程结构与最小完整练习

原课程把REQUIREMENT_SYSTEM_PROMPT、REQUIREMENT_USER_TEMPLATE放在prompts/requirement.prompt.ts，把ChatPromptTemplate.fromMessages放在requirement.prompt-builder.ts。服务方法promptPreview预览，promptToModel执行模型请求。生产接入继续沿该结构，本次先把同一过程放进独立练习文件便于看清。

学生创建：interview-training/labs/w1-d3/prompt-preview.ts。教师本轮只提供讲义中的代码，业务文件由学生创建。本例纯离线渲染，模型请求0次，无需密钥。

```ts
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
  audience: '后端开发者',
  input: '用户注册时必须绑定手机号，密码至少8位。',
};

const messages = await requirementPrompt.formatMessages(values);
console.log('系统消息：', messages[0].content);
console.log('用户消息：', messages[1].content);

const promptValue = await requirementPrompt.invoke(values);
console.log('完整预览：\n', promptValue.toString());
```

隔离练习复用services/chat已有依赖，因此使用明确相对路径；正常服务源文件按包名@langchain/core/prompts导入。本地对应文件路径已核对存在。此文件使用Bun运行顶层await，与此前练习方式一致。

从工作区根目录启动一次：

```powershell
cd 'C:\Users\Administrator\Desktop\newAgent\agent-course'
bun run './interview-training/labs/w1-d3/prompt-preview.ts'
```

预期：系统消息含“后端开发者”；用户消息含完整注册需求；完整预览包含System/Human角色和已填充内容。输出为确定性的模板文本。

原3.5.5接模型的位置如下，为后续阅读片段，model需由既有createChatModel初始化：

```ts
const messages = await requirementPrompt.formatMessages(values);
const response = await model.invoke(messages);
```

本次练习停在预览，接模型、解析、链和接口在后续目标实作。先检查渲染能验证变量与角色；模型内容质量在真实调用后检查。

## 失败处理和边界

占位符与变量对象键名对应：模板{input}需要values.input，改为values.text后缺少input，可能在类型检查或模板运行时报告错误；模型请求尚未发生。先检查变量名、漏传字段和空输入。

模板文本直接写JSON示例时，默认f-string占位符解析需要使用双花括号表达字面花括号。作为values.input传入的用户文本花括号按数据插入，正常填充不会再次递归解释它。模板渲染负责格式填充；输入真实性、权限和提示注入边界由相应检查与安全单元处理。

## 必背和面试标准答案

1. 提示模板集中保存任务规则和消息结构，通过占位符接收本轮变量。formatMessages把变量填成消息数组，再交给模型，便于复用和单独检查实际输入。
2. requirementPrompt.invoke执行模板渲染，返回PromptValue；model.invoke执行模型请求，返回模型消息；链的invoke在后续讲解，执行范围由链包含的步骤决定。
3. 缺少变量时先查占位符与对象键名；渲染正确但回答有问题时检查模型输入、Prompt规则、模型配置和输出依据。失败位置分开记录。

## 学生动作与教师验证

学生先创建并运行本文件；独立修改audience为产品经理，核对变化出现在哪条消息。排错阅读：把values.input改成text时，应在模板填充阶段定位缺少变量，未发起模型调用。学生真实输出与独立说明待交。

教师本地@langchain/core 1.2.11离线检查通过：两条消息、变量填充、invoke预览、缺少变量失败、输入字面花括号保留；供应商请求0次，临时文件0个。fromMessages和formatMessages类型定义已核对，无本例API弃用标记。参考：[官方消息模板示例](https://reference.langchain.com/javascript/langchain-core/prompts/HumanMessagePromptTemplate)。
