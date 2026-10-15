# 第三章：LangChain 起手——搭建第一条服务端能力链路

> 本章分支：`feat/first-chain`

第二章跑通了工程底座；第 2.5 章讲了 AI 怎样按阶段参与真实开发。有了这两层准备，第三章正式**把模型能力接进系统**：当一次简单的模型调用已经不够用时，怎样把它整理成一条**可维护、可复用、可测试**的能力链路。

LangChain 的作用不是给模型调用再包一层语法糖，而是把**提示模板、模型、输出解析、工具调用和链路编排**放进同一套编程模型里，让原本散落在业务代码里的 Prompt、解析逻辑和调用细节收束到清晰的位置。

递进节奏：
1. 把 LangChain 接进现有 Nest 服务端
2. 把散落的字符串提示整理成模板
3. 把模型输出收束为稳定字段
4. 接入工具调用，让模型能触发确定性校验
5. 把能力回收到业务接口，形成可测试的服务端入口

全章围绕一个任务：**从需求文本中抽取结构化字段 `action / constraints / entities`**。

**✅ 本章验收点**
- 理解并跑通 LangChain 服务端常用的几组 API
- 按顺序把模型调用、提示模板、输出解析、工具调用串到同一条链路
- 能力收束到 Nest Service / Controller，而不是停留在零散示例
- 最终落到可测试的业务接口：`POST /requirement/extract`

> 每个阶段都提供可交给 AI 执行的 Prompt，文中只保留关键代码。重点是掌握 API、理解设计思路、引导 AI 产出代码；AI 生成的方法名或实现细节可能有差异，按需微调。

**项目命名约定**
- 服务端：`services/chat`，端口 4001
- 前端：`clients/chat-web`，端口 3002
- 共享包：`@autix/contracts`
- 演示接口：`LlmController` 为 `@Controller('api/langchain')`，如 `POST /api/langchain/invoke`
- 业务入口：`POST /requirement/extract`

> ⚠️ **本地项目注意**：你的 `services/chat` 是 ESM 项目（`"type": "module"`），下文代码里的相对路径 import 需要补 `.js` 后缀，例如 `from './model.factory.js'`。

### 第一章概念 ↔ LangChain API 对照

（评论区读者建议补充，整理如下）

| 第一章概念 | 本章对应的 LangChain 能力 |
|---|---|
| system / user 消息分工 | `SystemMessage` / `HumanMessage` |
| Prompt 不写死在业务代码 | `prompts/` 目录 + `ChatPromptTemplate` |
| 统一模型调用层 `LLMClient` | `createChatModel()` 模型工厂 |
| 先定义返回结构 schema | 共享包里的 Zod `RequirementResultSchema` |
| 结构化输出 + 校验 | `withStructuredOutput()` |
| 封装成可复用模块 | `pipe()` 链 + `RequirementService` |

---

## 3.1 为什么要引入 LangChain

只发起一次最简单的模型调用，OpenAI SDK 就够了。进入业务系统后，问题会从"能不能调通"变成"能不能长期维护"：

- **提示内容会变多**：难维护的往往不是调用本身，而是分散在各文件里的提示词、变量拼接和输出要求 → **提示层**
- **模型结果要进入程序**：结果作为接口返回值、页面数据源、后续流程输入时，格式稳定性直接影响可用性 → **解析层 / 结构化输出**
- **系统需要工具与检索**：只靠提示词模型只能生成回答，不能调用外部系统；只靠模型已有知识也覆盖不了最新文档和内部资料 → **工具层 / 检索层**
- **多步骤要形成固定流程**：单步扩展成多步时，需要可组合、可复用、可测试的编排方式 → **链式编排 / pipe**

> 引入 LangChain 的重点不是"换一种写法调用模型"，而是把这些迟早会出现的工程问题**提前收口**。

### 先把任务定义清楚

比技术选型更重要的是任务定义。如果需求只写成"提取核心目标 / 限制 / 关键词"，很难稳定实现：核心目标边界是什么？关键词抽到什么粒度？同一段文本是否只有一个合理结果？测试断言什么？

所以本章固定在一个**可验证**的抽取任务上：

```typescript
{
  action: string;
  constraints: string[];
  entities: string[];
}
```

输入：`用户注册时必须绑定手机号，密码至少8位`

预期输出：
```json
{
  "action": "用户注册",
  "constraints": ["必须绑定手机号", "密码至少8位"],
  "entities": ["用户", "手机号", "密码"]
}
```

五个递进层次：
1. **模型层**：创建模型，理解 `invoke()` / `stream()` / `batch()` 的场景
2. **提示层**：把写死的长字符串整理成模板，用变量填充
3. **解析层**：让模型返回适合进入代码的结构，而不是自由文本
4. **工具层**：模型根据上下文决定是否调用校验工具
5. **收束层**：能力落回业务 Service / Controller，形成稳定可验证的接口

---

## 3.2 服务端承载模型能力的分工原则

沿用第二章的分层：
- `clients/chat-web`：只负责输入、展示和交互
- `services/chat`：组织模型调用、工具、检索与后续链路
- `packages/`：沉淀多处复用的共享定义

复杂度放在服务端的原因：
- API Key 不会暴露在浏览器
- 工具调用和检索过程更容易统一管理
- 日志、限流、缓存、重试、监控更好收口
- 后续多模型路由、RAG、MCP、Agent runtime 有明确落点

### 补充：为什么不用 Next 充当服务层底座

| 维度 | Next | Nest |
|---|---|---|
| 定位 | 应用层：渲染、路由、RSC/SSR、贴近 UI 的数据获取 | 服务层：模块化、DI、中间件/守卫/拦截器、业务域编排 |
| 性能与稳定性 | — | AI 请求多为长耗时、流式、重试/超时、工具与检索串联，适合统一治理 |
| 安全边界 | — | 模型/向量库/工具/MCP 凭证集中在后端，便于最小暴露、审计、限权 |
| 部署扩缩容 | 前端发布节奏 | 后端常需独立扩容、告警、超时策略 |
| 并发形态 | — | AI 请求更像服务编排，易演化出异步队列、后台任务、消费者 |

> **结论**：Next = 前端应用层 + BFF；Nest = 长期承载 AI 能力、业务编排、内部工具与系统集成的后端底座。

---

## 3.3 接入前的项目准备

### 3.3.1 安装依赖

```bash
bun add langchain @langchain/openai @langchain/core js-yaml \
  --cwd services/chat
```

共享层的 `zod` 沿用之前安装的版本。

### 3.3.2 配置分层：环境变量 + YAML

| 放在哪 | 放什么 | 原因 |
|---|---|---|
| **环境变量**（`.env` / Docker） | 令牌、密钥、外部服务地址 | 敏感、按环境变化 |
| **YAML 配置文件** | 模型参数、功能开关、检索配置 | 不敏感但会频繁调整 |
| **TypeScript 代码**（`prompts/`） | 提示模板、业务逻辑 | 需要版本管理和类型约束 |

**令牌与密钥：环境变量**

开发阶段 `services/chat/.env`：
```bash
OPENAI_API_KEY=sk-xxxx
OPENAI_BASE_URL=https://api.amux.ai/v1
EMBEDDING_API_KEY=sk-xxxx
VECTOR_DB_URL=http://localhost:6333
VECTOR_DB_API_KEY=
```

生产阶段通过 Docker Compose 注入，不落盘任何密钥文件：
```yaml
services:
  chat:
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - OPENAI_BASE_URL=${OPENAI_BASE_URL}
      - EMBEDDING_API_KEY=${EMBEDDING_API_KEY}
      - VECTOR_DB_URL=${VECTOR_DB_URL}
      - VECTOR_DB_API_KEY=${VECTOR_DB_API_KEY}
```

> ⚠️ 原则：令牌、密钥、外部服务地址一律走环境变量，不写进 YAML 和代码。`.env` 必须加入 `.gitignore`，CI/CD 和 Docker 通过 secrets 或环境变量注入。

**运行参数：YAML**

`services/chat/config/langchain.yaml`（原文缩进在网页上丢失，以下已修正）：
```yaml
llm:
  provider: openai
  model: gpt-5.4
  temperature: 0
  maxTokens: 800

retrieval:
  enabled: true
  topK: 3

tools:
  enableConstraintCheck: true
  enableEntityLookup: true

features:
  enableStructuredOutput: true
  enableStreaming: true
```

> ⚠️ YAML 冒号后必须有空格（`temperature: 0`，不能写 `temperature:0`），缩进只能用空格。

### 3.3.3 配置加载器

`services/chat/src/config/load-langchain-config.ts`

```typescript
import * as fs from 'node:fs';
import * as path from 'node:path';
import * as yaml from 'js-yaml';

export type LangChainAppConfig = {
  llm: {
    provider: string;
    model: string;
    temperature: number;
    maxTokens: number;
  };
  retrieval: { enabled: boolean; topK: number };
  tools: {
    enableConstraintCheck: boolean;
    enableEntityLookup: boolean;
  };
  features: {
    enableStructuredOutput: boolean;
    enableStreaming: boolean;
  };
};

export function loadLangChainConfig(): LangChainAppConfig {
  const filePath = path.join(
    process.cwd(), 'config', 'langchain.yaml',
  );
  const raw = fs.readFileSync(filePath, 'utf8');
  return yaml.load(raw) as LangChainAppConfig;
}

export function getApiKeys() {
  return {
    openaiApiKey: process.env.OPENAI_API_KEY ?? '',
    openaiBaseUrl: process.env.OPENAI_BASE_URL,
    embeddingApiKey:
      process.env.EMBEDDING_API_KEY ??
      process.env.OPENAI_API_KEY ?? '',
    vectorDbUrl: process.env.VECTOR_DB_URL,
    vectorDbApiKey: process.env.VECTOR_DB_API_KEY,
  };
}
```

---

## 3.4 模型调用基础

### 🤖 AI 生成代码 Prompt（对应 3.3 + 3.4）

```
在现有 monorepo 的 services/chat 下，完成 LangChain 的接入准备与模型调用基础，严格按以下要求执行：

前置：
- 在 services/chat 安装依赖：langchain @langchain/openai @langchain/core js-yaml
- 在 services/chat/.env 中配置：OPENAI_API_KEY, OPENAI_BASE_URL, EMBEDDING_API_KEY, VECTOR_DB_URL, VECTOR_DB_API_KEY
- .env 加入 .gitignore

1. 配置层：
   - 新建 services/chat/config/langchain.yaml，只放运行参数：llm、retrieval、tools、features
   - 新建 services/chat/src/config/load-langchain-config.ts

2. 统一模型工厂：
   - 新建 services/chat/src/llm/model.factory.ts
   - 从 YAML 读取模型参数，从 getApiKeys() 读取令牌和 baseURL

3. NestJS 骨架 + 三种调用路由：
   - 新建 llm.module.ts / llm.service.ts / llm.controller.ts（@Controller('api/langchain')）
   - 实现：POST invoke / POST stream / POST batch
   - 输入统一使用：'用户注册时必须绑定手机号，密码至少8位'

约束：
- 令牌/密钥/服务地址一律走 process.env
- 所有路由的 SystemMessage 角色为"需求结构化抽取助手"
- 不要在 Service 里直接 new ChatOpenAI，统一用 createChatModel()
- 所有能力以 Service 方法 + Controller 路由形式暴露
```

### 3.4.1 统一模型工厂

模型初始化统一收口到工厂函数，不散落在各个 Service 中。

`services/chat/src/llm/model.factory.ts`

```typescript
import { ChatOpenAI } from '@langchain/openai';
import {
  loadLangChainConfig,
  getApiKeys,
} from '../config/load-langchain-config';

export function createChatModel() {
  const config = loadLangChainConfig();
  const keys = getApiKeys();

  return new ChatOpenAI({
    model: config.llm.model,
    temperature: config.llm.temperature,
    maxTokens: config.llm.maxTokens,
    openAIApiKey: keys.openaiApiKey,
    configuration: keys.openaiBaseUrl
      ? { baseURL: keys.openaiBaseUrl }
      : undefined,
  });
}
```

NestJS 骨架（后面的能力都以 Service + Controller 形式落地，便于测试和替换）：

```typescript
// llm.module.ts
@Module({
  providers: [LlmService, RequirementService],
  controllers: [LlmController],
  exports: [LlmService, RequirementService],
})
export class LlmModule {}

// llm.service.ts
@Injectable()
export class LlmService {
  private model = createChatModel();
}

// llm.controller.ts
@Controller('api/langchain')
export class LlmController {
  constructor(
    private readonly llmService: LlmService,
    private readonly requirementService: RequirementService,
  ) {}
}
```

### 3.4.2 invoke()：单次调用

适合：一次请求只要一个完整结果；先打通"输入 → 模型 → 输出"主流程；暂不考虑流式和批量。

```typescript
import {
  HumanMessage, SystemMessage, type BaseMessage,
} from '@langchain/core/messages';

async invokeDemo(input: string): Promise<string> {
  const messages: BaseMessage[] = [
    new SystemMessage('你是一名需求结构化抽取助手'),
    new HumanMessage(
      `请从下面文本中抽取 action、constraints、entities：\n${input}`,
    ),
  ];
  const response = await this.model.invoke(messages);
  return response.content.toString();
}
```

```typescript
@Post('invoke')
async invoke(@Body() body: { input: string }) {
  const result = await this.llmService.invokeDemo(body.input);
  return { result };
}
```

```bash
curl -s -X POST http://localhost:4001/api/langchain/invoke \
  -H "Content-Type: application/json" \
  -d '{"input": "用户注册时必须绑定手机号，密码至少8位"}'
```

### 3.4.3 stream()：流式调用

适合结果不必等全部生成完才展示，前端可逐步渲染。

```typescript
async streamDemo(input: string) {
  return this.model.stream([
    new SystemMessage('你是一名需求结构化抽取助手'),
    new HumanMessage(`请逐步分析并输出结构化抽取结果：\n${input}`),
  ]);
}
```

Controller（SSE 方式）：
```typescript
@Post('stream')
async stream(
  @Body() body: { input: string },
  @Res() res: Response,
) {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');

  const stream = await this.llmService.streamDemo(body.input);
  for await (const chunk of stream) {
    res.write(chunk.content);
  }
  res.end();
}
```

### 3.4.4 batch()：批量处理

同一套处理逻辑一次跑多条。

```typescript
async batchDemo(inputs: string[]) {
  const messageGroups = inputs.map((input) => [
    new SystemMessage('你是一名需求结构化抽取助手'),
    new HumanMessage(`请抽取 action、constraints、entities：\n${input}`),
  ]);
  const responses = await this.model.batch(messageGroups);
  return responses.map((item) => item.content.toString());
}
```

```typescript
@Post('batch')
async batch(@Body() body: { inputs: string[] }) {
  return { results: await this.llmService.batchDemo(body.inputs) };
}
```

### 3.4.5 三种调用方式怎么选

**invoke()：一次拿到最终结果（默认选择）**
- 适合接口型能力，需要一次性返回可断言的 JSON 或文本
- 适合链路早期，先跑通主路径再叠加解析、工具、检索
- 请求边界清晰，便于做重试、超时、缓存、幂等
- 不太适合：内容很长、前端想边生成边展示

**stream()：边生成边返回（强调体验）**
- 适合前端逐字渲染，降低体感延迟
- 适合输出较长、需要实时记录或支持用户中断的场景
- 注意：流式**更难做结构化消费和断言测试**。要稳定 JSON 通常先 `invoke()` 拿结构化结果，再决定解释性内容是否流式

**batch()：一次处理多条（强调吞吐与成本）**
- 适合离线任务、定时任务、数据回填
- 适合同一 Prompt 处理多条相似输入，提升吞吐
- 适合评测与回归：一组样本批量跑，对比输出差异
- 注意：失败处理更精细（顺序对应、部分失败重试、单条超时对整体的影响）

---

## 3.5 提示模板化改造

### 🤖 AI 生成代码 Prompt（对应 3.5）

```
在 services/chat 的 LangChain 层中，把提示内容抽成模板，并提供最小模板渲染与调用示例：

1. 提示模板：
   - 新建 services/chat/src/llm/prompts/requirement.prompt.ts
   - 导出 REQUIREMENT_SYSTEM_PROMPT
   - 导出 REQUIREMENT_USER_TEMPLATE（包含 {input} 占位符）

2. 模板构建器：
   - 新建 services/chat/src/llm/requirement.prompt-builder.ts
   - 用 ChatPromptTemplate.fromMessages() 组装 system + human 消息

3. 示例路由：
   - POST prompt-preview：只渲染模板，不调模型
   - POST prompt-to-model：模板 → formatMessages → 模型调用

测试输入统一为：'用户注册时必须绑定手机号，密码至少8位'
```

### 3.5.1 字符串拼接的局限

接口和任务变多后，直接拼字符串会越来越难维护：提示重复、改动分散、变量插入不直观。趁早把提示抽到专门目录：

```
services/chat/src/llm/prompts/
├─ requirement.prompt.ts
├─ classify.prompt.ts
└─ retrieve-answer.prompt.ts
```

### 3.5.2 最小提示模板

把"系统角色"与"用户输入"从一开始就分开。

```typescript
// prompts/requirement.prompt.ts
export const REQUIREMENT_SYSTEM_PROMPT = `
你是一名"需求结构化抽取助手"。

你的任务是：
从输入文本中提取结构化字段。

严格要求：
1. 不允许编造信息
2. action 必须是唯一核心动作（动词+对象）
3. constraints 只保留明确约束（必须 / 至少 / 不得 / 不能）
4. entities 只提取文本中真实出现的名词
5. 如果不存在某字段，返回空数组

输出必须符合 schema，不要输出解释
`.trim();

export const REQUIREMENT_USER_TEMPLATE = `
请抽取结构化信息：

输入：
{input}
`.trim();
```

### 3.5.3 ChatPromptTemplate.fromMessages()

把 system 与 human 两段消息组装成可复用提示。

```typescript
// requirement.prompt-builder.ts
import { ChatPromptTemplate } from '@langchain/core/prompts';
import {
  REQUIREMENT_SYSTEM_PROMPT,
  REQUIREMENT_USER_TEMPLATE,
} from './prompts/requirement.prompt';

export const requirementPrompt = ChatPromptTemplate.fromMessages([
  ['system', REQUIREMENT_SYSTEM_PROMPT],
  ['human', REQUIREMENT_USER_TEMPLATE],
]);
```

### 3.5.4 先看渲染结果

送给模型前，先单独验证变量替换和消息结构是否正确。

```typescript
async promptPreview(input: string) {
  const promptValue = await requirementPrompt.invoke({ input });
  return { rendered: promptValue.toString() };
}

@Post('prompt-preview')
async promptPreview(@Body() body: { input: string }) {
  return this.llmService.promptPreview(body.input);
}
```

### 3.5.5 模板转成消息数组再调模型

调用路径从"手写消息"切换成"模板 → 消息 → 模型"。

```typescript
async promptToModel(input: string) {
  const messages = await requirementPrompt.formatMessages({ input });
  const response = await this.model.invoke(messages);
  return { result: response.content };
}

@Post('prompt-to-model')
async promptToModel(@Body() body: { input: string }) {
  return this.llmService.promptToModel(body.input);
}
```

---

## 3.6 基础调用链的构建

### 🤖 AI 生成代码 Prompt（对应 3.6）

```
在 services/chat 的 LangChain 层中，用 pipe() 构建最小调用链：

1. 调用链：
   - 新建 services/chat/src/llm/requirement.chain.ts
   - 用 requirementPrompt.pipe(model).pipe(new StringOutputParser()) 构建链
   - 导出 requirementChain

2. 新增路由：POST chain-invoke / POST chain-stream / POST chain-batch

输入统一为：'用户注册时必须绑定手机号，密码至少8位'
```

### 3.6.1 pipe() 与 StringOutputParser

当步骤以固定顺序反复出现，就用 `pipe()` 串成一条链。最小链由三段组成：**提示模板 → 模型 → 输出解析**。

```typescript
// requirement.chain.ts
import { StringOutputParser } from '@langchain/core/output_parsers';
import { createChatModel } from './model.factory';
import { requirementPrompt } from './requirement.prompt-builder';

const model = createChatModel();
const parser = new StringOutputParser();

export const requirementChain =
  requirementPrompt.pipe(model).pipe(parser);
```

### 3.6.2 链同样支持 invoke / stream / batch

```typescript
// 一次返回
async chainInvoke(input: string) {
  return { result: await requirementChain.invoke({ input }) };
}

// 流式（Controller 同 3.4.3，写入 chunk 即可，parser 已转成字符串）
async chainStream(input: string) {
  return requirementChain.stream({ input });
}

// 批量
async chainBatch(inputs: string[]) {
  const results = await requirementChain.batch(
    inputs.map((input) => ({ input })),
  );
  return results.map((result, i) => ({ index: i + 1, result }));
}
```

### 3.6.3 什么时候该上链

和直接调模型相比，链适合：输入前总要先走模板填充；输出后总要接统一解析；同一套流程在多个接口复用；希望把"提示 + 模型 + 解析"当成一个整体来调用、测试和替换。

**chain.invoke()**：结果完整返回，而且背后已经是一条固定流水线。例如需求抽取接口、文案标准化改写、分类打标、多处复用的服务层逻辑。

**chain.stream()**：同一条稳定流程需要边产出边展示。例如长文本分析、前端即时反馈、后台实时透出过程。实用思路：**先把固定流程写成 chain，再根据产品需要选 invoke 还是 stream**，业务流程和返回方式分开。

**chain.batch()**：同一条标准链在多条输入上执行。例如历史数据回填、导入前预处理、改了 prompt/模型后的回归评测、低峰期离线任务。它往往是把"能跑的 AI 功能"推进到"可规模化处理的数据流程"的关键一步。

> **判断标准**：连续两次以上写出"同一个 prompt + 同一个 model + 同一个 parser"的组合，就该收成 chain。从这时起，你要维护的不再是某次调用，而是一条业务流程。

---

## 3.7 结构化输出与程序化消费

### 🤖 AI 生成代码 Prompt（对应 3.7）

```
在 services/chat 的 LangChain 层中，让模型返回固定字段格式：

1. 共享字段定义（packages/contracts/src/index.ts）：
   - RequirementSchema
   - RequirementResultSchema
   - 导出 RequirementResult

2. 结构化服务（services/chat/src/llm/requirement.service.ts）：
   - 复用 prompts/requirement.prompt.ts 中的常量
   - 用 ChatPromptTemplate.fromMessages() 构建提示
   - 方法 extract(input: string)：
     - prompt.formatMessages({ input })
     - model.withStructuredOutput(RequirementResultSchema)
     - 返回结构化结果

3. 新增路由：POST structured
```

### 3.7.1 自由文本的局限

调用流程整理清楚了，但输出仍是自由文本的话，进入程序后价值有限。只要结果要作为接口返回值、下游输入或测试断言，自由文本的不稳定就会成为问题。

### 3.7.2 共享字段结构

字段结构沉淀到共享 contract：

```typescript
// packages/contracts/src/index.ts
import { z } from 'zod';

export const RequirementSchema = z.object({
  input: z.string().min(1),
});

export const RequirementResultSchema = z.object({
  action: z.string().describe('唯一核心动作'),
  constraints: z.array(z.string()).describe('明确约束条件'),
  entities: z.array(z.string()).describe('关键实体'),
});

export type RequirementResult =
  z.infer<typeof RequirementResultSchema>;
```

### 3.7.3 withStructuredOutput()

让模型直接朝着 schema 输出，而不是依赖后置字符串清洗。

```typescript
// requirement.service.ts
@Injectable()
export class RequirementService {
  private model = createChatModel();

  private prompt = ChatPromptTemplate.fromMessages([
    ['system', REQUIREMENT_SYSTEM_PROMPT],
    ['human', REQUIREMENT_USER_TEMPLATE],
  ]);

  async extract(input: string): Promise<RequirementResult> {
    const messages = await this.prompt.formatMessages({ input });
    const structuredModel = this.model.withStructuredOutput(
      RequirementResultSchema,
    );
    return structuredModel.invoke(messages);
  }
}
```

```typescript
@Post('structured')
async structured(@Body() body: { input: string }) {
  return this.requirementService.extract(body.input);
}
```

> ⚠️ 若出现解析错误，可在 prompt 中明确要求返回 JSON，或额外实现 JSON 解析兜底。即使声明了返回 JSON，仍可能夹杂解释文本，要靠提示约束 + 解析兜底 + 测试样例一起处理。
>
> ⚠️（评论区经验）部分第三方中转 API 不支持 `withStructuredOutput`，会达不到课程效果。

到这一层，LangChain 才进入工程化语境：**只有结构稳定，测试、回归、复用和下游编排才有基础。**

---

## 3.8 工具调用机制的接入

### 🤖 AI 生成代码 Prompt（对应 3.8）

```
在 services/chat 的 LangChain 层中，接入工具调用机制：

1. 工具定义（services/chat/src/llm/tools/basic.tools.ts）：
   - check_constraint_validity
   - lookup_entity_definition

2. 在 LlmService + LlmController 中新增路由：
   - POST tool-bind
   - POST tool-loop

输入统一使用需求抽取场景。
```

### 3.8.1 工具的本质：可调用函数

结构化输出后字段已经稳定，但模型本身仍然只能生成内容。要在抽取之后校验约束、补充规则说明，就需要接入工具。

> **模型负责决策，工具负责提供确定性结果。**

```typescript
// tools/basic.tools.ts
import { z } from 'zod';
import { tool } from '@langchain/core/tools';

export const checkConstraintValidityTool = tool(
  async ({ constraint }: { constraint: string }) => {
    const passed = /必须|至少|不得|不能/.test(constraint);
    return {
      constraint,
      passed,
      reason: passed ? '命中明确约束模式' : '不属于明确约束表达',
    };
  },
  {
    name: 'check_constraint_validity',
    description: '校验一条约束是否属于明确约束表达',
    schema: z.object({ constraint: z.string() }),
  },
);

export const lookupEntityDefinitionTool = tool(
  async ({ entity }: { entity: string }) => {
    const map: Record<string, string> = {
      用户: '系统中的账号主体',
      手机号: '用于身份绑定与验证的联系字段',
      密码: '用于登录认证的安全凭证',
    };
    return { entity, definition: map[entity] ?? '未命中内置定义' };
  },
  {
    name: 'lookup_entity_definition',
    description: '查询实体在业务中的定义说明',
    schema: z.object({ entity: z.string() }),
  },
);
```

### 3.8.2 bindTools()

```typescript
async toolBindDemo(input: string) {
  const modelWithTools = this.model.bindTools([
    checkConstraintValidityTool,
    lookupEntityDefinitionTool,
  ]);

  const response = await modelWithTools.invoke([
    new SystemMessage('你可以按需要调用工具来校验约束和查询实体定义。'),
    new HumanMessage(`请分析下面需求：${input}`),
  ]);

  return {
    result: response.content.toString(),
    toolCalls: response.tool_calls,
  };
}
```

### 3.8.3 理解 tool_calls

绑定工具后，模型**不一定立刻给出最终答案**。很多时候它会先通过 `tool_calls` 声明：准备调用哪个工具、参数是什么、调用 id 是多少。

从这里开始，模型不再只是"生成一段文本"，而是在参与一个**可审计的执行流程**。

### 3.8.4 手动实现工具执行闭环

完整闭环：**声明调用 → 执行工具 → 回填结果 → 生成最终答复**。

```typescript
import {
  HumanMessage, SystemMessage, ToolMessage, type BaseMessage,
} from '@langchain/core/messages';
import type { StructuredToolInterface } from '@langchain/core/tools';

async toolLoopDemo(input: string) {
  const tools: StructuredToolInterface[] = [
    checkConstraintValidityTool,
    lookupEntityDefinitionTool,
  ];
  const toolMap = Object.fromEntries(tools.map((t) => [t.name, t]));
  const modelWithTools = this.model.bindTools(tools);

  const messages: BaseMessage[] = [
    new SystemMessage('你可以调用工具来帮助完成需求抽取后的校验。'),
    new HumanMessage(
      `先抽取 action、constraints、entities，再按需要调用工具：${input}`,
    ),
  ];

  // 1. 模型声明要调用哪些工具
  const firstResponse = await modelWithTools.invoke(messages);
  messages.push(firstResponse);

  // 2. 系统执行工具，把结果回填为 ToolMessage
  for (const toolCall of firstResponse.tool_calls ?? []) {
    const targetTool = toolMap[toolCall.name];
    if (!targetTool) continue;
    const toolResult = await targetTool.invoke(toolCall.args);
    messages.push(new ToolMessage({
      tool_call_id: toolCall.id ?? '',
      content: JSON.stringify(toolResult),
    }));
  }

  // 3. 模型基于工具结果生成最终答复
  const finalResponse = await modelWithTools.invoke(messages);
  return { result: finalResponse.content };
}
```

### 3.8.5 工具调用适合解决什么问题

> **判断**：当答案依赖**外部事实、外部规则或真实动作**时，就该上工具；否则优先用 prompt / 结构化输出解决。

四类常见场景：
- **规则校验**：抽取后再验（如 `check_constraint_validity`）
- **事实查询**：实体定义、配置、订单状态等必须查系统/查库（如 `lookup_entity_definition`）
- **流程编排**：模型做路由/决策，工具做执行（工单分流、表单审核、缺失项检查）
- **高风险闭环**：先产出 tool_calls → 系统执行 → ToolMessage 回填 → 再生成答复，可审计、可限权、可定位失败点

后面的 RAG、MCP、Agent runtime，本质也是在扩展"**模型负责判断，系统负责执行**"的边界。

---

## 3.9 能力收束与统一入口

### 🤖 AI 生成代码 Prompt（对应 3.9）

```
把前面所有 LangChain 能力收回到 Nest 服务端，并更新前端页面：

1. 服务层：services/chat/src/llm/requirement.service.ts
   - @Injectable() 类 RequirementService
   - 对外提供 extract(input: string): Promise<RequirementResult>

2. Controller：services/chat/src/app.controller.ts
   - POST /requirement/extract 接收 { input: string }

3. 前端页面：textarea + 提交按钮 + JSON 结果展示
   - 默认输入：'用户注册时必须绑定手机号，密码至少8位'

4. 增加测试文件：services/chat/test/requirement.spec.ts
```

### 3.9.1 按业务域拆分 Service

能力变多后，Service 拆分从"技术演示"切换到"业务域承载"：不用 `SummaryService` 这类泛化命名，直接落到真实业务名 `RequirementService`（代码同 3.7.3）。

### 3.9.2 统一入口 Controller

Controller 收口成统一入口，而不是继续暴露一堆演示路由：

```typescript
// app.controller.ts
@Controller()
export class AppController {
  constructor(
    private readonly appService: AppService,
    private readonly requirementService: RequirementService,
  ) {}

  @Get('health')
  getHealth() { return this.appService.getHealth(); }

  @Get('hello')
  getHello() { return this.appService.getHello(); }

  // 3.9 能力收束：整条链路落到统一业务入口
  @Post('/requirement/extract')
  async extract(@Body() body: { input: string }) {
    return this.requirementService.extract(body.input);
  }
}
```

测试 `services/chat/test/requirement.spec.ts`：

```typescript
import { describe, it, expect } from 'bun:test';
import { RequirementService } from '../src/llm/requirement.service';

// 会发起真实模型调用，默认跳过。需要时：RUN_LLM_E2E=1 bun test
const runIf = process.env.RUN_LLM_E2E ? it : it.skip;

describe('Requirement Extract', () => {
  runIf('should extract correctly', async () => {
    const service = new RequirementService();
    const result = await service.extract(
      '用户注册时必须绑定手机号，密码至少8位',
    );

    // 结构化约定：字段类型稳定
    expect(typeof result.action).toBe('string');
    expect(result.action.length).toBeGreaterThan(0);
    expect(Array.isArray(result.constraints)).toBe(true);
    expect(Array.isArray(result.entities)).toBe(true);
    expect(result.constraints.length).toBeGreaterThan(0);
    // 措辞可能不同，只断言语义命中
    expect(JSON.stringify(result)).toContain('手机号');
  }, 30000);
});
```

> 模型返回的措辞会随模型/温度波动（action 可能是"用户注册"也可能是"绑定手机号"）。所以**断言只校验结构化约定与关键语义命中，不锁死具体字符串**——这正是 `withStructuredOutput` 要保证的部分。
>
> 注：你的项目 Nest 脚手架默认用 vitest，`bun:test` 是 Bun 自带的测试框架，二者 API 相近，按项目实际选用。

### 3.9.3 前端页面的职责边界

```tsx
// clients/chat-web/src/app/page.tsx
'use client';
import { useState } from 'react';
import type { RequirementResult } from '@autix/contracts';

export default function Home() {
  const [input, setInput] = useState(
    '用户注册时必须绑定手机号，密码至少8位',
  );
  const [result, setResult] = useState<RequirementResult | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit() {
    setLoading(true);
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL}/requirement/extract`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ input }),
        },
      );
      setResult(await res.json());
    } finally {
      setLoading(false);
    }
  }

  return (
    <main style={{ padding: 24, maxWidth: 720 }}>
      <h1>Requirement Extract Demo</h1>
      <textarea value={input} rows={8} style={{ width: '100%' }}
        onChange={(e) => setInput(e.target.value)} />
      <button onClick={handleSubmit} disabled={loading}
        style={{ marginTop: 12 }}>
        {loading ? '提取中…' : '提取'}
      </button>
      <pre style={{ marginTop: 16 }}>
        {JSON.stringify(result, null, 2)}
      </pre>
    </main>
  );
}
```

前端只做三件事：
- **输入需求文本**：只负责采集，不做预处理
- **请求统一接口**：原样交给服务端，不关心背后是哪个模型、哪条链、什么工具
- **展示结构化 JSON**：直接渲染，不做二次解析或字段校验

> 模型规则、结构化抽取、工具调用、测试与校验都留在服务端。**前端越薄，后端能力迭代时需要联动改动的地方就越少。**

---

## 3.10 本章小结

### 每一层解决了什么问题

| 层 | 解决的问题 | 手段 |
|---|---|---|
| 模型层（3.4） | 怎样把模型接进服务端 | 统一工厂 + invoke / stream / batch |
| 提示层（3.5） | 提示内容怎样不失控 | 模板化，拆到独立目录，变量填充 |
| 链式层（3.6） | 重复步骤怎样统一管理 | `pipe()` 串起模板、模型、解析 |
| 解析层（3.7） | 模型输出怎样进入程序 | 共享 Zod schema + `withStructuredOutput()` |
| 工具层（3.8） | 模型只会生成、不会执行 | `bindTools()` + 工具执行闭环 |
| 收束层（3.9） | 能力怎样变成业务入口 | `RequirementService` + `POST /requirement/extract` |

### 核心判断标准

- **什么时候上模板？** 同一段提示词出现在两个以上地方，或改一次提示要动多个文件
- **什么时候上链？** "模板 → 模型 → 解析"已稳定，并在多个接口或任务中反复调用
- **什么时候上结构化输出？** 结果要作为接口返回值、下游输入或测试断言，而不只是给人读
- **什么时候上工具？** 答案依赖外部事实、外部规则或真实动作
- **什么时候收束？** 分散示例已验证通过，下一步要被其他模块、团队、环境稳定调用

### 后续章节衔接

- **RAG**：回答前先检索相关文档，解决"知识覆盖不足"
- **MCP**：工具通过标准协议接入外部系统，解决"能力边界封闭"
- **Agent Runtime**：模型根据上下文动态决定下一步，解决"流程不够灵活"

> 核心原则不变：**先把任务定义清楚，再把能力放到正确的层，最后收束成可测试、可迭代的入口。**

---

## 评论区值得记下的经验

- **Windows 上 Bun 的兼容问题**：有读者做到 3.6 时 `bun run build / dev` 持续报错，回退代码、重装依赖都无效，最后把 `bunfig.toml` 里的 `linker = "isolated"` 改成 `hoisted` 并重新安装才解决。你也在 Windows 上，遇到类似的顽固安装/构建问题时可以考虑这个方向
- **中转 API 可能不支持 `withStructuredOutput`**，会导致 3.7 / 3.9 达不到课程效果
- **学习成本**：作者建议可以用 MiniMax、GLM 这类 coding plan 配合 Claude 来验证学习，控制费用
