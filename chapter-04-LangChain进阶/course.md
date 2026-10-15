# 第四章：LangChain 进阶——记忆、工具与多 Agent

> 本章分支：`feat/agent-memory-tools`

前三章完成了 LangChain 基础链路：模型调用、提示模板、链式编排、结构化输出和工具调用，都落到了可测试的业务接口。但这条链路**仍以单次请求为中心**：每轮输入独立处理，不保留上一轮对话，不主动读取业务文件，也无法把复杂任务拆给多个角色协作。

本章补齐四类进阶能力：
1. **会话记忆**：支撑多轮需求澄清与上下文延续
2. **业务工具**：读取需求单、规范文档，并输出分析报告
3. **文本向量化**：为后续语义检索与 RAG 打基础
4. **Multi-Agent**：角色拆分与固定编排的工程实现

由于第五章的多 Agent 流水线工作在需求分析业务域，本章把原先的电商退货示例统一改写为需求分析域，五个 Agent 为 **extract / clarify / analysis / risk / summary**，与后续章节保持一致。

> LangChain 在 Agent 构建上更强调以 `createAgent()` 作为标准入口。本章为了与前几章工程主线一致、完整呈现从多轮上下文到多角色协作的演进，仍以 messages、tools、embeddings、vector stores 和 fixed-workflow 多 Agent 作为讲解主线。

### 贯穿案例

需求单 **REQ-2026-001**——「为需求分析对话提供会话记忆」。多轮输入固定为：

1. 我们想做一个需求分析助手，希望它能记住多轮对话。
2. 需求单号是 REQ-2026-001。
3. 目标用户是需求分析师和产品经理，长对话要能自动裁剪上下文。
4. 帮我判断这个需求是否完整，并产出一份需求分析报告。

后续各节围绕这条需求依次接入 Memory、Tools、Embeddings 和 Multi-Agent，最后收敛为统一的 `analyze()` 接口。

### ✅ 本章验收点

- 理解 `RunnableWithMessageHistory` 的工作机制，跑通会话级多轮对话
- 掌握 `trimMessages` 的裁剪策略，在长对话下控制 Token 成本
- 实现业务工具（`query_requirement`、`read_file`、`write_file`），读取真实数据并写出制品
- 完成文本向量化（本地小模型），搭建最小嵌入 + 向量库链路
- 理解 Multi-Agent 的角色拆分与 Fixed Workflow 编排模式
- 用 5 Agent 示例完成"抽取 → 澄清 → 分析 → 风控 → 汇总"全流程
- 信息不足时显式产出澄清问题（`clarificationQuestions`）
- 所有能力收束为统一的 `analyze()` 服务接口

### 和第三章的衔接

| 第三章已有 | 第四章在此基础上加 |
|---|---|
| 单次调用、单轮闭环 | 会话记忆，多轮上下文延续 |
| 本地演示工具（正则校验、字典查询） | 业务工具：查需求单、读规范、写报告，带路径沙箱 |
| `pipe()` 一条链 | 多条链分别扮演不同角色，由编排服务串起来 |
| tool-loop 只循环一轮 | 工具循环带上限，可多轮调用 |

---

## 4.1 多轮需求澄清为什么会失真

第三章跑通的是"单轮闭环"：用户提交输入，组装 prompt，必要时调工具，整理成结构化输出。输入完整、流程清晰，每次请求可以独立测试。

真实的需求沟通**不会一次性给出全部判断条件**：先表达诉求，再补充需求单号、目标用户、约束条件，中途还可能调整关注点。判断所需的信息分散在连续多轮对话里。如果仍然"每轮独立处理"，链路在工程上能跑，业务理解上会逐渐失真。

以上面 4 轮对话为例，如果每次只把当前输入发给模型：
- 第二轮只说"需求单号是 REQ-2026-001"，模型不知道这条需求要解决什么问题
- 第三轮补充目标用户和自动裁剪时，模型不知道这是在补充需求约束
- 第四轮要求判断完整性并出报告，模型拿不到前文，很难给出完整结论

> 第三章解决"单次调用如何做对"，本章解决"**多次调用之间如何不断线**"。

决定多轮沟通质量的关键，不是某一轮回复是否完整，而是系统能否把分散在多轮中的需求单号、目标用户和核心诉求**稳定地组织成同一个任务上下文**。在 LangChain 里，这个上下文最自然的承载方式是 **messages**：它是跨模型统一的消息抽象，也是接入 Memory、裁剪历史、组织多轮链路的基础。

---

## 4.2 Memory：用 RunnableWithMessageHistory 保持上下文

### 🤖 AI 生成代码 Prompt（对应 4.2）

```
在 services/chat 的 LangChain 层中，接入 Memory 机制，严格按以下要求执行：

1. 安装依赖（如需要）：langchain 相关 memory 模块

2. Memory 服务：
   - 新建 services/chat/src/llm/memory/runnable-memory.service.ts
   - 实现 RunnableWithMessageHistory + InMemoryChatMessageHistory 的多轮对话
   - 实现 trimMessages 消息裁剪版本（maxTokens: 2000, strategy: 'last'）
   - 每个版本支持 sessionId 隔离
   - 对外暴露：chat(sessionId, input)、getHistory(sessionId)、appendMessage(sessionId, human, ai)、clearSession(sessionId)

3. 新增路由（@Controller('api/memory')）：
   - POST chat：接收 { sessionId, input }，返回多轮对话结果
   - GET history/:sessionId：返回当前会话的历史记录
   - DELETE history/:sessionId：清除指定会话记忆

业务场景：需求分析助手
测试场景（同一 sessionId "s1" 依次发送）：
第一轮：'我们想做一个需求分析助手，希望它能记住多轮对话'
第二轮：'需求单号是 REQ-2026-001'
第三轮：'帮我判断这个需求是否完整'
```

本节处理两项能力：用 `RunnableWithMessageHistory` 注入会话历史，用 `trimMessages` 控制长对话成本。旧式 `BufferMemory`、`SummaryMemory` 不再展开——在当前 LangChain JS 体系中，基于消息历史的实现更统一，也更贴近应用层接口设计。

### 4.2.1 会话历史的读取与注入

`RunnableWithMessageHistory` 是 LangChain 提供的**会话历史包装层**，把历史消息的读取、注入和保存统一抽象到 Runnable 链路中。核心是**按 sessionId 隔离不同会话**，并把读写接口封装成可复用的服务方法。

下面把"历史注入"和"消息裁剪"合并成一份服务：进入 prompt 前先用 `trimMessages` 裁剪历史，再交给 `RunnableWithMessageHistory` 注入。

```typescript
import { Injectable } from '@nestjs/common';
import {
  ChatPromptTemplate,
  MessagesPlaceholder,
} from '@langchain/core/prompts';
import {
  RunnableWithMessageHistory,
  RunnablePassthrough,
} from '@langchain/core/runnables';
import { InMemoryChatMessageHistory } from '@langchain/core/chat_history';
import { trimMessages, type BaseMessage } from '@langchain/core/messages';
import { createChatModel } from '../model.factory';

@Injectable()
export class RunnableMemoryService {
  private store = new Map<string, InMemoryChatMessageHistory>();
  private model = createChatModel();

  private prompt = ChatPromptTemplate.fromMessages([
    ['system', '你是一名需求分析助手，请结合历史对话理解用户诉求并给出回答。'],
    new MessagesPlaceholder('history'),
    ['human', '{input}'],
  ]);

  // 长对话下控制 Token：保留最近且必要的上下文
  private trimmer = trimMessages({
    maxTokens: 2000,
    strategy: 'last',
    tokenCounter: this.model,
    includeSystem: true,
    allowPartial: false,
  });

  // 进入 prompt 之前先对历史做裁剪
  private chain = RunnablePassthrough.assign({
    history: (input: { input: string; history?: BaseMessage[] }) =>
      this.trimmer.invoke(input.history ?? []),
  })
    .pipe(this.prompt)
    .pipe(this.model);

  private getSessionHistory = (sessionId: string) => {
    if (!this.store.has(sessionId)) {
      this.store.set(sessionId, new InMemoryChatMessageHistory());
    }
    return this.store.get(sessionId)!;
  };

  private withHistory = new RunnableWithMessageHistory({
    runnable: this.chain,
    getMessageHistory: this.getSessionHistory,
    inputMessagesKey: 'input',
    historyMessagesKey: 'history',
  });

  async chat(sessionId: string, input: string) {
    const response = await this.withHistory.invoke(
      { input },
      { configurable: { sessionId } },
    );
    return { response: response.content };
  }

  async getHistory(sessionId: string) {
    return this.getSessionHistory(sessionId).getMessages();
  }

  async appendMessage(sessionId: string, human: string, ai: string) {
    const history = this.getSessionHistory(sessionId);
    await history.addUserMessage(human);
    await history.addAIMessage(ai);
  }

  clearSession(sessionId: string) {
    this.store.delete(sessionId);
  }
}
```

这一步的核心变化：**接口从围绕"单次请求"工作，转向围绕"会话"工作**。对需求单 REQ-2026-001，系统可以持续保留当前需求、目标用户、上下文约束等关键信息。

> 📌 **当前项目的实际做法**：`RunnableWithMessageHistory` 用于解释 LangChain 的消息历史注入机制；实际落地时，会话历史持久化到数据库 `messages` 表，通过 `MessageService` / `DbChatHistory` 转成 `BaseMessage[]`，生产链路不依赖进程内 `InMemoryChatMessageHistory`（见第五章）。实际流程：`ConversationController.chat()` 收到输入 → `MessageService.addMessage()` 保存用户消息 → `SearchService.similaritySearch()` 做 RAG 检索 → `OrchestratorService.streamOrchestrate()` 执行分析 → assistant 响应写回 `messages` 表。

### 4.2.2 消息裁剪与 Token 成本控制

只保留历史还不够。对话一旦拉长，原始历史会持续占用上下文窗口。`trimMessages` 提供可配置的裁剪策略，在保留必要上下文的同时控制 Token 消耗：

```typescript
const trimmer = trimMessages({
  maxTokens: 2000,
  strategy: 'last',
  tokenCounter: model,
  includeSystem: true,
  allowPartial: false,
});

const chain = RunnablePassthrough.assign({
  history: (input: { history?: BaseMessage[] }) =>
    trimmer.invoke(input.history ?? []),
}).pipe(prompt).pipe(model);
```

随着轮次增加，系统**优先保留最近且与需求判断相关的信息**，而不是把所有历史原样塞回模型。

> 📌 **Memory 工程化小结**
> - `sessionId`：隔离不同会话
> - `getHistory()`：读取当前上下文
> - `appendMessage()`：把最终结论写回历史（**优先用这个，而不是让模型重跑一遍对话**）
> - `clearSession()`：清理会话状态
> - `trimMessages()`：长对话下控制成本
> - 存储可替换：`InMemoryChatMessageHistory` 是开发阶段实现，生产可切到 Redis / 数据库，接口不变

### 🧪 验证（对应 4.2）

同一 sessionId 依次发送四轮：

```bash
curl -X POST http://localhost:4001/api/memory/chat \
  -H "Content-Type: application/json" \
  -d '{"sessionId":"s1","input":"我们想做一个需求分析助手，希望它能记住多轮对话"}'

curl -X POST http://localhost:4001/api/memory/chat \
  -H "Content-Type: application/json" \
  -d '{"sessionId":"s1","input":"需求单号是 REQ-2026-001"}'

curl -X POST http://localhost:4001/api/memory/chat \
  -H "Content-Type: application/json" \
  -d '{"sessionId":"s1","input":"目标用户是需求分析师和产品经理，长对话要能自动裁剪"}'

curl -X POST http://localhost:4001/api/memory/chat \
  -H "Content-Type: application/json" \
  -d '{"sessionId":"s1","input":"帮我判断这个需求是否完整"}'

# 查看历史（应含 8 条：4 human + 4 ai）
curl "http://localhost:4001/api/memory/history/s1"

# 清除会话
curl -X DELETE "http://localhost:4001/api/memory/history/s1"
```

验收标准：
- 第四轮回复能识别需求单号和目标用户，不会失忆重新询问
- `getHistory` 返回 8 条消息
- 清除会话后再次 `getHistory` 返回空数组

---

## 4.3 Tools：读取需求单、规范文档，并写出分析报告

### 🤖 AI 生成代码 Prompt（对应 4.3）

```
在 services/chat 的 LangChain 层中，接入文件系统与业务查询工具，严格按以下要求执行：

1. 工具定义：
   - 新建 services/chat/src/llm/tools/business.tools.ts
   - 使用 tool() + zod schema 定义以下工具：
     - query_requirement：根据需求单号读取 workspace/requirements/{requirementId}.json
     - read_file：读取 workspace/ 下指定路径的文件内容（规范、标准等）
     - write_file：将内容写入 workspace/ 下指定路径（分析报告、制品）
   - 所有文件操作限制在 workspace/ 目录下（safePath 沙箱校验）

2. 文件系统服务：
   - 新建 services/chat/src/llm/filesystem/filesystem.service.ts
   - 绑定上述工具到模型
   - 实现完整的工具执行闭环（参考第三章 3.8 的 tool-loop 模式）

3. 新增路由（@Controller('api/files')）：
   - POST chat：接收 { input }，模型可按需调用工具读写文件

业务场景：需求分析助手
测试场景（workspace 内的相对路径，不带 workspace/ 前缀）：
- '查询需求单 REQ-2026-001 的详情'
- 如需验证 read_file，可先在 workspace 下补充 standards/requirement-spec.md
- '把需求判断结论写入 reports/REQ-2026-001-analysis.md'
```

接入 Memory 后系统能保留上下文，但仍然拿不到需求单详情、规范文档和验收标准。下一步要让模型**通过受控工具读取业务数据，而不是依赖提示词补全事实**。

本节重点不是通用的 read_file / write_file，而是先定义需求分析场景真正需要的业务工具。对当前案例，`query_requirement(requirementId)` 比"任意读文件"更接近真实系统的能力边界。

### 4.3.1 三类业务工具：查询、读取与写入

```typescript
import fs from 'node:fs';
import path from 'node:path';
import { z } from 'zod';
import { tool } from '@langchain/core/tools';

const WORKSPACE_ROOT = path.join(process.cwd(), 'workspace');

// 路径沙箱：所有文件操作必须落在 workspace/ 内，防止路径逃逸
export function safePath(filePath: string) {
  const resolved = path.resolve(WORKSPACE_ROOT, filePath);
  if (!resolved.startsWith(WORKSPACE_ROOT)) {
    throw new Error('路径不允许逃逸工作目录');
  }
  return resolved;
}

export const queryRequirementTool = tool(
  async ({ requirementId }: { requirementId: string }) => {
    const full = safePath(`requirements/${requirementId}.json`);
    if (!fs.existsSync(full)) {
      return { error: `需求 ${requirementId} 不存在` };
    }
    return JSON.parse(fs.readFileSync(full, 'utf8'));
  },
  {
    name: 'query_requirement',
    description: '根据需求单号查询需求详情、提出方、目标与约束',
    schema: z.object({
      requirementId: z.string().describe('需求单号，例如 REQ-2026-001'),
    }),
  },
);

export const readFileTool = tool(
  async ({ filePath }: { filePath: string }) => {
    const full = safePath(filePath);
    if (!fs.existsSync(full)) return { error: '文件不存在' };
    return { content: fs.readFileSync(full, 'utf8') };
  },
  {
    name: 'read_file',
    description: '读取需求规范、标准或其他业务文件',
    schema: z.object({
      filePath: z.string().describe('相对于 workspace 的文件路径'),
    }),
  },
);

export const writeFileTool = tool(
  async ({ filePath, content }: { filePath: string; content: string }) => {
    const full = safePath(filePath);
    fs.mkdirSync(path.dirname(full), { recursive: true });
    fs.writeFileSync(full, content, 'utf8');
    return { success: true, path: filePath };
  },
  {
    name: 'write_file',
    description: '写入需求分析报告或制品',
    schema: z.object({
      filePath: z.string().describe('相对于 workspace 的文件路径'),
      content: z.string().describe('要写入的内容'),
    }),
  },
);
```

三个工具对应三个明确动作——**查需求、读规范、写制品**：
- `query_requirement('REQ-2026-001')`：读取需求详情、目标与约束
- `read_file('standards/requirement-spec.md')`：读取需求规范依据（需自行补充该文件）
- `write_file('reports/REQ-2026-001-analysis.md', content)`：把结论落到报告文件

### 4.3.2 工具调用的分工：数据查询与制品输出

如果模型只返回一段聊天回复，分析结果很难沉淀；当系统能把需求判断写入 `reports/`，输出才具备后续复核、归档和协作价值。

沿用第三章分工：**模型决定是否调用、调用哪个、何时继续；工具返回确定性结果**。三类职责：
- `query_requirement`：读业务数据，返回事实
- `read_file`：读规范标准，返回规则依据
- `write_file`：执行写入动作，生成持久化制品

文件系统服务用 tool-loop 把三类工具串起来：

```typescript
import { Injectable } from '@nestjs/common';
import {
  HumanMessage, ToolMessage, type BaseMessage,
} from '@langchain/core/messages';
import type { StructuredToolInterface } from '@langchain/core/tools';
import { createChatModel } from '../model.factory';
import {
  queryRequirementTool, readFileTool, writeFileTool, safePath,
} from '../tools/business.tools';
import fs from 'node:fs';
import path from 'node:path';

@Injectable()
export class FilesystemService {
  private tools: StructuredToolInterface[] = [
    queryRequirementTool,
    readFileTool,
    writeFileTool,
  ];
  private toolMap = new Map(this.tools.map((t) => [t.name, t]));
  private model = createChatModel().bindTools(this.tools);

  // 工具循环：模型决定调用 → 执行 → 回灌结果 → 直到模型给出最终回答
  async chat(input: string) {
    const messages: BaseMessage[] = [new HumanMessage(input)];
    const usedTools: string[] = [];

    for (let i = 0; i < 5; i++) {
      const ai = await this.model.invoke(messages);
      messages.push(ai);

      const calls = ai.tool_calls ?? [];
      if (calls.length === 0) {
        return { response: ai.content, usedTools };
      }

      for (const call of calls) {
        usedTools.push(call.name);
        const selected = this.toolMap.get(call.name);
        const result = selected
          ? await selected.invoke(call.args)
          : { error: `未知工具 ${call.name}` };
        messages.push(new ToolMessage({
          content: JSON.stringify(result),
          tool_call_id: call.id ?? call.name,
        }));
      }
    }
    return { response: '工具调用超出上限', usedTools };
  }

  // 供 analyze() 直接落盘报告，无需经过工具循环
  writeReport(filePath: string, content: string) {
    const full = safePath(filePath);
    fs.mkdirSync(path.dirname(full), { recursive: true });
    fs.writeFileSync(full, content, 'utf8');
    return filePath;
  }
}
```

> ⚠️ **安全提醒**：`safePath()` 的路径沙箱校验**必须放在工具内部**，不能依赖模型"自觉遵守"。生产环境里，写操作还应接入审计日志，并进一步限制可写目录。`write_file` 这种通用写入工具在教学中便于演示，生产中必须收敛到明确业务目录，不能让模型决定任意文件路径。当前项目更推荐通过业务服务写入 artifact、message 或数据库记录，而不是把文件系统写入暴露为通用能力。

### 🧪 验证（对应 4.3）

仓库预置示例需求单 `services/chat/workspace/requirements/REQ-2026-001.json`（练习项目需自行创建）；默认未预置 `standards/requirement-spec.md`。先验证查询、写入与越权拒绝：

```bash
# 查询需求单（触发 query_requirement）
curl -X POST http://localhost:4001/api/files/chat \
  -H "Content-Type: application/json" \
  -d '{"input":"查询需求单 REQ-2026-001 的详情"}'

# 写入需求分析（触发 write_file）
curl -X POST http://localhost:4001/api/files/chat \
  -H "Content-Type: application/json" \
  -d '{"input":"把以下内容写入 reports/REQ-2026-001-analysis.md：需求 REQ-2026-001 核心功能明确（会话记忆+长对话裁剪），目标用户清晰，需求基本完整，建议进入设计阶段"}'

# 确认文件落盘
cat services/chat/workspace/reports/REQ-2026-001-analysis.md

# 越权路径测试（应返回错误，不写入）
curl -X POST http://localhost:4001/api/files/chat \
  -H "Content-Type: application/json" \
  -d '{"input":"把内容写入 ../../../etc/passwd"}'
```

验收标准：工具可正常调用并返回结果；报告文件存在且内容完整；越权路径请求返回"路径不允许逃逸工作目录"错误。

---

## 4.4 Embeddings + Vector Store：先建立语义基础

### 🤖 AI 生成代码 Prompt（对应 4.4）

```
在 services/chat 的 LangChain 层中，接入向量化能力，严格按以下要求执行：

1. 安装依赖：
   - @xenova/transformers（本地嵌入模型运行时）
   - @langchain/classic（包含 MemoryVectorStore）

2. 嵌入服务：
   - 新建 services/chat/src/llm/embedding/embedding.service.ts
   - 继承 LangChain 的 Embeddings 抽象类，模型：Xenova/paraphrase-multilingual-MiniLM-L12-v2
   - 对外暴露：embedQuery(text) 和 embedDocuments(documents)

3. 向量存储服务：
   - 新建 services/chat/src/llm/embedding/vector-store.service.ts
   - 使用 MemoryVectorStore（内存存储，无需外部服务）
   - 实现 addTexts(texts: string[])
   - 实现 search(query: string, k: number)

4. 新增路由（@Controller('api/embedding')）：
   - POST embed：接收 { text }，返回向量维度与向量
   - POST store：接收 { texts }，存入向量库
   - POST search：接收 { query, k }，返回相似文档

初始灌库文档：需求规范片段、验收标准片段、约束说明片段
```

本节暂不展开完整 RAG，也不实现问答链路，而是先完成更基础的一层：**把需求规范、验收标准和约束说明转换为可语义召回的对象**。

### 4.4.1 本地嵌入模型：Xenova/paraphrase-multilingual-MiniLM-L12-v2

Hugging Face 上的多语言句向量模型，由 `@xenova/transformers` 驱动，可在 Node.js 中**纯本地运行**，不调远程 API。

**"本地模型"和"内存存储"是两个概念**：
- **模型权重文件**：首次运行自动从 Hugging Face 下载，持久缓存到本地磁盘（默认 `~/.cache/huggingface/`），之后启动直接从磁盘加载
- **运行时内存**：推理时占用约 90MB，进程退出释放
- **向量存储**：本章用 `MemoryVectorStore` 做内存演示；生产链路用 PostgreSQL + pgvector 持久化（见第五章），重启不丢

**为什么选这个模型**

| 特性 | 说明 |
|---|---|
| 多语言 | 原生支持中文、英文等 50+ 语言，中文效果较好 |
| 轻量 | 约 90MB，推理快，本地可用 |
| 无 API 依赖 | 完全离线，不消耗 token，不需要密钥 |
| 向量维度 | 384 维，适合小规模知识库 |

**局限**：384 维的语义精度不如 OpenAI `text-embedding-3-small`（1536 维）或 `text-embedding-3-large`（3072 维）。选它主要为降低教学门槛。上层接口不依赖具体实现，换成其他 embeddings 只需替换底层，调用方式不变。

### 4.4.2 嵌入接口：embedQuery 与 embedDocuments

LangChain 的 `Embeddings` 抽象只暴露两个方法：
- `embedQuery()`：在线检索时对**单条**输入编码
- `embedDocuments()`：离线**批量**灌库

底层实现可随时替换，上层调用不变。本章直接继承 `Embeddings` 抽象类，实例可以直接传给 `MemoryVectorStore`。

> 📌 LangChain community 也提供 `HuggingFaceTransformersEmbeddings` 封装，但本项目没用，原因是当前依赖组合中 `@huggingface/transformers` / `onnxruntime-node` 存在版本兼容风险。本章直接用 `@xenova/transformers` 调用 pipeline，并做 mean pooling + L2 单位化。

```typescript
import { Injectable } from '@nestjs/common';
import { Embeddings } from '@langchain/core/embeddings';
import { pipeline, mean_pooling } from '@xenova/transformers';

@Injectable()
export class EmbeddingService extends Embeddings {
  private embedder: any = null;
  private readonly modelName =
    'Xenova/paraphrase-multilingual-MiniLM-L12-v2';

  constructor() {
    super({});
  }

  // 延迟初始化：模型下载一次后复用
  private async getEmbedder() {
    if (!this.embedder) {
      this.embedder = await pipeline('feature-extraction', this.modelName);
    }
    return this.embedder;
  }

  async embedDocuments(texts: string[]): Promise<number[][]> {
    const embedder = await this.getEmbedder();
    const cleanTexts = texts.map((t) => t.replace(/\n/g, ' '));

    const rawOutput = (await embedder(cleanTexts)) as any;
    const inputs = embedder.tokenizer(cleanTexts, {
      padding: true,
      truncation: true,
    });
    // mean pooling（按 attention_mask 加权）+ L2 单位化（余弦相似度 = 点积）
    const pooled = mean_pooling(rawOutput, inputs.attention_mask);
    return pooled.normalize(2, -1).tolist();
  }

  async embedQuery(text: string): Promise<number[]> {
    const [vector] = await this.embedDocuments([text]);
    return vector;
  }
}
```

### 4.4.3 向量存储与相似度检索

用 LangChain v1 的 `MemoryVectorStore`（来自 `@langchain/classic`）做最小可用的相似度检索，把 `EmbeddingService` 直接传进去：

```typescript
import { Injectable } from '@nestjs/common';
import { MemoryVectorStore } from '@langchain/classic/vectorstores/memory';
import { Document } from '@langchain/core/documents';
import { EmbeddingService } from './embedding.service';

@Injectable()
export class VectorStoreService {
  private store: MemoryVectorStore;

  constructor(private readonly embeddings: EmbeddingService) {
    this.store = new MemoryVectorStore(this.embeddings);
  }

  async addTexts(texts: string[]) {
    const docs = texts.map((text) => new Document({ pageContent: text }));
    await this.store.addDocuments(docs);
    return { added: texts.length };
  }

  async search(query: string, k = 3) {
    const results = await this.store.similaritySearchWithScore(query, k);
    return results.map(([doc, score]) => ({
      content: doc.pageContent,
      score,
    }));
  }
}
```

> 📌 **当前项目实际依赖**
> - `@xenova/transformers`：本地运行 embedding 模型
> - `@langchain/classic`：本章 `MemoryVectorStore` 内存演示
> - PostgreSQL + pgvector（第五章）：持久化向量存储与相似度检索
>
> `MemoryVectorStore` 进程重启即丢失，只适合教学。LangChain.js v1 中应从 `@langchain/classic/vectorstores/memory` 引入。

第五章会替换为真实文档处理流程：`ChunkService` 用 `RecursiveCharacterTextSplitter` 切分文本，`EmbeddingService` 生成 384 维向量写入 `document_chunks.embedding`，查询时 `SearchService` 用 pgvector 的 `<=>` 距离运算排序。

本章先把几类需求知识片段灌进向量库：需求规范片段、验收标准片段、约束说明片段。目的是把业务说明从普通文本**转换成可语义召回的对象**，后面无论是 RAG、长期记忆还是需求知识库，都建立在这一层之上。

### 🧪 验证（对应 4.4）

首次调用会自动下载嵌入模型（约 90MB），需要联网。

```bash
# 单条向量化（返回 dimension 和 vector）
curl -X POST http://localhost:4001/api/embedding/embed \
  -H "Content-Type: application/json" \
  -d '{"text":"需求分析助手需要记住多轮对话"}'

# 灌库
curl -X POST http://localhost:4001/api/embedding/store \
  -H "Content-Type: application/json" \
  -d '{"texts":["需求规范：核心功能、目标用户、业务目标三者齐全才算需求完整","验收标准：同一会话连续多轮对话应保持上下文一致，不重复提问","约束说明：单会话上下文不超过 2000 tokens，会话之间互相隔离"]}'

# 语义搜索
curl -X POST http://localhost:4001/api/embedding/search \
  -H "Content-Type: application/json" \
  -d '{"query":"怎样判断一个需求是否完整","k":3}'
```

验收标准：
- embed 返回 `dimension: 384` 和对应向量
- store 返回 `{"added":3}`
- search 第一条结果与"需求完整性判断"相关（包含核心功能/目标用户/业务目标的规范片段）

---

## 4.5 Multi-Agent：把需求分析拆成 5 个专职角色

### 🤖 AI 生成代码 Prompt（对应 4.5）

```
在 services/chat 的 LangChain 层中，实现 Multi-Agent 固定编排，严格按以下要求执行：

1. Agent 提示词：
   - 新建 services/chat/src/llm/prompts/requirement.prompts.ts
   - 用 ChatPromptTemplate 定义五个需求分析 Agent 的提示词：
     extractPrompt / clarifyPrompt / analysisPrompt / riskPrompt / summaryPrompt

2. 子 Agent 定义：
   - 新建 services/chat/src/llm/agents/sub-agents.ts
   - 每个 Agent = prompt.pipe(model).pipe(StringOutputParser)：
     - extractAgent：从用户描述抽取结构化需求字段，输出 JSON
     - clarifyAgent：判断是否需要澄清并生成问题，输出 JSON
     - analysisAgent：多维度需求分析（功能分解/用户故事/验收标准/依赖/建议）
     - riskAgent：风险识别与评估
     - summaryAgent：汇总生成最终需求分析报告

3. 编排服务：
   - 新建 services/chat/src/llm/agents/orchestrator.service.ts
   - 实现 fixed workflow：抽取 → 澄清判断 → 并行（分析 + 风控）→ 汇总
   - 需要澄清时，返回 clarificationQuestions 并终止流程
   - 失败时返回 fallback: 'manual_review'
   - 返回字段：mode、status、clarificationQuestions、usedAgents、fallback、steps、report

4. 新增路由（@Controller('api/agents')）：
   - POST orchestrate：接收 { input }，执行多 Agent 协作

业务场景：需求分析
测试输入：'开发一个面向需求分析师的会话记忆系统，支持多轮澄清并自动裁剪长对话上下文'
```

**不是所有任务都要多 Agent**。如果一个 prompt 配合少量工具已经能稳定完成，就不需要拆。只有任务存在清晰的阶段划分、角色分工或后续扩展需求时，多 Agent 才有引入价值。当前需求分析链路可自然拆成五类：

| Agent | 职责 |
|---|---|
| `extractAgent` | 抽取需求类型、核心功能、目标用户、约束等结构化字段 |
| `clarifyAgent` | 判断信息是否充分，必要时生成澄清问题 |
| `analysisAgent` | 功能分解、用户故事、验收标准等多维度分析 |
| `riskAgent` | 识别模糊性、范围、技术、业务风险 |
| `summaryAgent` | 汇总输出最终需求分析报告 |

### 4.5.1 子 Agent 的结构与职责划分

**每个 Agent 都是一条独立的小链**，有自己的 system prompt、输入变量和输出格式。和第三章的链式编排是同一种思路，只是把不同职责分给了不同的链。提示词集中放在 `prompts/requirement.prompts.ts`，`sub-agents.ts` 只负责组装：

```typescript
import { StringOutputParser } from '@langchain/core/output_parsers';
import { createChatModel } from '../model.factory';
import {
  extractPrompt,
  clarifyPrompt,
  analysisPrompt,
  riskPrompt,
  summaryPrompt,
} from '../prompts/requirement.prompts';

const model = createChatModel();
const parser = new StringOutputParser();

export const extractAgent = extractPrompt.pipe(model).pipe(parser);
export const clarifyAgent = clarifyPrompt.pipe(model).pipe(parser);
export const analysisAgent = analysisPrompt.pipe(model).pipe(parser);
export const riskAgent = riskPrompt.pipe(model).pipe(parser);
export const summaryAgent = summaryPrompt.pipe(model).pipe(parser);
```

各提示词的输出约定：
- `extractPrompt`：结构化需求 JSON（`requirementType / coreFeature / targetUsers / businessGoal / constraints / priority / isComplete / missingFields`）
- `clarifyPrompt`：`{ needsClarification, questions }`
- `analysisPrompt` / `riskPrompt`：Markdown 小节
- `summaryPrompt`：汇总完整报告，预留 `retrievedContext` 变量

> ⚠️ 原文未给出五个提示词的完整内容（"完整内容见仓库"），练习时需要按上述输出约定自己编写。

### 4.5.2 Fixed Workflow 编排实现

当前流程相对稳定：**先抽取字段 → 判断是否需要澄清 → 信息不足则短路返回澄清问题 → 否则并行执行分析和风控 → 汇总为报告**。

```typescript
import { Injectable } from '@nestjs/common';
import {
  extractAgent, clarifyAgent, analysisAgent, riskAgent, summaryAgent,
} from './sub-agents';

// LLM 偶尔会带 ```json 代码块包裹，做一次容错解析
function parseJsonLoose(raw: string): any {
  const cleaned = raw
    .trim()
    .replace(/^```(?:json)?/i, '')
    .replace(/```$/i, '')
    .trim();
  return JSON.parse(cleaned);
}

@Injectable()
export class OrchestratorService {
  async orchestrate(input: string) {
    try {
      const extractResult = await extractAgent.invoke({ input });

      // 澄清判断：信息不足时短路返回
      const clarifyRaw = await clarifyAgent.invoke({ extractResult, input });
      let clarificationQuestions: string[] = [];
      try {
        const clarify = parseJsonLoose(clarifyRaw);
        if (clarify?.needsClarification && Array.isArray(clarify.questions)) {
          clarificationQuestions = clarify.questions;
        }
      } catch {
        // 澄清结果解析失败时不阻塞主流程，按"无需澄清"继续
      }

      if (clarificationQuestions.length > 0) {
        return {
          mode: 'fixed_workflow',
          status: 'need_clarification',
          clarificationQuestions,
          usedAgents: ['extractAgent', 'clarifyAgent'],
          fallback: 'ask_user',
        };
      }

      const [analysisResult, riskResult] = await Promise.all([
        analysisAgent.invoke({ extractResult, input }),
        riskAgent.invoke({ extractResult, input }),
      ]);

      const report = await summaryAgent.invoke({
        input,
        extractResult,
        analysisResult,
        riskResult,
        retrievedContext: '无相关参考文档',
      });

      return {
        mode: 'fixed_workflow',
        clarificationQuestions: [],
        usedAgents: [
          'extractAgent', 'clarifyAgent', 'analysisAgent',
          'riskAgent', 'summaryAgent',
        ],
        fallback: null,
        steps: {
          extract: extractResult,
          analysis: analysisResult,
          risk: riskResult,
        },
        report,
      };
    } catch (error) {
      return {
        mode: 'fixed_workflow',
        clarificationQuestions: [],
        usedAgents: ['extractAgent'],
        fallback: 'manual_review',
        report: '分析流程失败，请转人工复核。',
        error: String(error),
      };
    }
  }
}
```

`summaryPrompt` 预留的 `retrievedContext` 用于接入知识库检索结果。本章没有 RAG，传入占位值；第五章接入 pgvector 后替换为真实召回片段。

### 4.5.3 其他编排模式参考

**Router（分流路由）**：先分类再处理。主 Agent 识别意图后路由到专项 Agent。例：用户消息可能是功能需求、非功能需求、缺陷反馈或咨询，路由 Agent 判断类型后分别交给需求分析 Agent、缺陷处理 Agent。

**Supervisor（动态调度）**：流程不固定，主 Agent 根据每一步结果实时决定下一步调谁。例：处理复杂需求时先抽取，发现涉及合规就临时调"合规审查 Agent"，发现高风险变更再调"风控 Agent"，流程是动态生成的。

**Handoff（控制权交接）**：多阶段、需要角色切换。一个 Agent 处理完后把控制权和上下文一起交给下一个。例：需求收集 Agent 整理好需求交给评审 Agent，评审完再交给通知 Agent，每个 Agent 只管自己职责，结束时主动交棒。

**Planner-Executor（规划执行分离）**：任务复杂、步骤不确定。Planner 先把目标拆成子任务列表，Executor 逐步执行，异常时回传 Planner 重新规划。例："把这份 PRD 拆成可排期的需求清单"。

本章不逐一实现这些模式，先把 Fixed Workflow 讲透：当前需求分析链路步骤是确定的，不需要动态调度或分类路由。先把固定流程跑通、跑稳，才是扩展的基础。

> 📌 **什么时候适合上多 Agent**
> - 一个 prompt 配合工具就能稳定解决 → 不需要多 Agent
> - 任务天然分阶段、分角色、分工具 → 适合
> - 需要不同工具集或不同模型配置 → 适合
> - 需要较强扩展性、后续持续增加角色 → 非常适合

### 🧪 验证（对应 4.5）

```bash
# 场景 A：信息完整，触发完整五 Agent 编排
curl -X POST http://localhost:4001/api/agents/orchestrate \
  -H "Content-Type: application/json" \
  -d '{"input":"开发一个面向需求分析师的会话记忆系统，支持多轮澄清并自动裁剪长对话上下文"}'

# 场景 B：信息不足，触发澄清问题返回
curl -X POST http://localhost:4001/api/agents/orchestrate \
  -H "Content-Type: application/json" \
  -d '{"input":"做个系统"}'
```

验收标准：
- 场景 A：`usedAgents` 包含全部 5 个 Agent，`report` 含报告结论，`fallback` 为 `null`
- 场景 B：`status` 为 `need_clarification`，`clarificationQuestions` 非空，`usedAgents` 仅含 extractAgent 和 clarifyAgent

---

## 4.6 统一入口：把 Memory、Tools、Embeddings、Multi-Agent 收成一个接口

### 🤖 AI 生成代码 Prompt（对应 4.6）

```
把第四章所有能力收回到 Nest 服务端统一入口，严格按以下要求执行：

1. 模块注册：
   - 新建 services/chat/src/llm/advanced.module.ts
   - 注册 RunnableMemoryService、EmbeddingService、VectorStoreService、FilesystemService、OrchestratorService、AdvancedAnalysisService
   - 在 AppModule 中 import AdvancedModule

2. 统一分析服务：
   - 新建 services/chat/src/llm/advanced-analysis.service.ts
   - 实现 analyze(sessionId: string, input: string)：
     1. 调用 OrchestratorService 执行多 Agent 分析
     2. 如果需要澄清，直接返回澄清问题
     3. 否则将报告写入 reports/ 目录
     4. 用 appendMessage() 写回最终结论（不重新调用模型）
     5. 返回完整分析报告

3. 统一 Controller：
   - 在 services/chat/src/llm/advanced.controller.ts 中统一承载 MemoryController、FilesystemController、EmbeddingController、AgentsController、AdvancedController
   - AdvancedController 使用 @Controller('api/advanced')
   - POST analyze：接收 { sessionId, input }，返回完整分析报告

测试场景（同一 sessionId 依次发送前三轮，再发第四轮触发 analyze）：
第四轮：'帮我判断这个需求是否完整，并产出一份需求分析报告'
```

前面的能力已分别验证。最后一步是整理成统一业务入口，避免停留在分散的 demo 接口上。`analyze()` 的职责：
1. 调用 Orchestrator 做多 Agent 分析
2. 需要澄清时直接返回澄清问题
3. 否则把报告写到 `reports/`
4. 用 `appendMessage()` 把最终结论写回会话记忆

```typescript
import { Injectable } from '@nestjs/common';
import { OrchestratorService } from './agents/orchestrator.service';
import { FilesystemService } from './filesystem/filesystem.service';
import { RunnableMemoryService } from './memory/runnable-memory.service';

export type AnalyzeResult =
  | { needsClarification: true; questions: string[] }
  | {
      needsClarification: false;
      report: string;
      reportPath: string;
      usedAgents: string[];
    };

@Injectable()
export class AdvancedAnalysisService {
  constructor(
    private readonly orchestrator: OrchestratorService,
    private readonly filesystem: FilesystemService,
    private readonly memory: RunnableMemoryService,
  ) {}

  async analyze(sessionId: string, input: string): Promise<AnalyzeResult> {
    const result = await this.orchestrator.orchestrate(input);

    if (result.status === 'need_clarification') {
      return {
        needsClarification: true,
        questions: result.clarificationQuestions,
      };
    }

    const report = result.report ?? '分析未生成报告';
    const reportPath = this.filesystem.writeReport(
      `reports/${sessionId}-${Date.now()}.md`,
      report,
    );
    // 用 appendMessage 写回结论，不重新调用模型
    await this.memory.appendMessage(sessionId, input, report);

    return {
      needsClarification: false,
      report,
      reportPath,
      usedAgents: result.usedAgents,
    };
  }
}
```

`FilesystemService.writeReport()` 同样走 `safePath` 沙箱，供 `analyze()` 直接落盘，无需经过工具循环。

> ⚠️ **关键细节**：写回记忆时优先用 `appendMessage(sessionId, input, report)`，把"用户输入 + 最终结论"作为一轮完整消息写入历史，**而不是把原始输入重新交给模型执行一次**。既保留上下文，又避免不必要的模型调用。

### 🧪 验证（对应 4.6）

```bash
curl -X POST http://localhost:4001/api/advanced/analyze \
  -H "Content-Type: application/json" \
  -d '{"sessionId":"demo","input":"帮我判断这个需求是否完整，并产出一份需求分析报告：开发一个面向需求分析师的会话记忆系统，支持多轮澄清并自动裁剪长对话上下文"}'

# 验证报告落盘（文件名形如 demo-<时间戳>.md）
ls services/chat/workspace/reports/

# 验证 Memory 写回了最终结论
curl "http://localhost:4001/api/memory/history/demo"
```

验收标准：返回完整 `report` 与 `reportPath`；`reports/` 下存在对应报告且内容一致；`getHistory` 最后一条 AI 消息是报告内容，而非模型重新生成的聊天回复。

完成统一入口后，同一条需求的处理链路形成闭环：**历史可以延续，需求单可以查询，规范可以读取，分析可以拆解，结果可以落盘，结论可以写回记忆**。系统不再只是单次问答接口，而是具备持续对话、制品沉淀和流程追踪能力的业务系统接口。

---

## 4.7 本章小结

| 能力 | 做了什么 | 解决什么 |
|---|---|---|
| **Memory** | `RunnableWithMessageHistory` 保持会话上下文 + `trimMessages` 控制 Token | 多轮对话信息断裂 |
| **Tools** | `query_requirement` / `read_file` / `write_file`，带路径沙箱 | 模型拿不到真实数据，结论无法沉淀为制品 |
| **Embeddings + Vector Store** | 本地多语言小模型向量化，存入 `MemoryVectorStore` | 为语义检索和 RAG 打基础（第五章换 pgvector） |
| **Multi-Agent** | 抽取、澄清、分析、风控、汇总五个 Agent，Fixed Workflow 串联 | 复杂任务分阶段分角色，信息不足时提前返回澄清问题 |

最终通过统一的 `analyze()` 接口，把多 Agent 分析、报告落盘与记忆写回收敛为一条端到端链路。系统从一次性问答接口，变成**可持续对话、可追溯制品的业务处理单元**。

---

## 评论区值得记下的经验

- **AI 按 Prompt 生成的代码差异很大**：同一 Prompt 每个人生成出来的文件和实现都不一样，项目越复杂差异越大，运行结果和课程示例也对不上。作者后续按章节分支补了 demo 代码。练习时以实际跑通为准，不要硬对课程截图
- **4.4 的 `vector-store.service.ts` 等部分文件原文没给全**，仓库最终产物里也不一定有
- **端口问题**：有读者按课程 curl 一直 404，发现作者中途改过端口。以自己项目实际端口为准（本练习项目后端是 4001）
- 五个 Agent 的提示词原文没有给出完整内容，需要自己按输出约定编写
