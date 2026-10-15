# 第五章：从 Mock 到生产——数据库设计与向量化落库

> 本章分支：`feat/db-vector`

第四章完成了 Memory、Tools、Embeddings 与 Multi-Agent 的能力验证，但这些实现仍是 demo 形态：
- `InMemoryChatMessageHistory` 服务重启就丢失
- `MemoryVectorStore` 进程退出就清空
- `workspace/requirements/*.json` 是手写的 mock 数据
- 系统没有用户身份，也没有数据隔离

学习验证够用，但系统要服务多个用户、长期运行、支持历史回溯与知识库复用，就必须把会话、文件、向量和任务状态迁移到**可持久、可管理、可隔离**的存储体系中。

本章完成从 demo 到生产形态的关键改造：**数据库建模、会话持久化、文档上传、向量化落库、任务通知，以及端到端分析链路串联**。

### 命名、路径与数据模型约定

采用仓库真实命名：`services/chat`（NestJS，端口 4001）。

- **chat 库不建 User 表**：用户系统由 user-system 微服务维护，chat 服务只保存 String 类型的 `userId`，不建跨服务外键
- 表名用 **snake_case 复数**：`conversations` / `messages` / `documents` / `document_chunks` / `task_events`
- `messages.role` 用枚举 `MessageRole { USER, ASSISTANT }`，与 LangChain 的 `HumanMessage` / `AIMessage` 映射
- `document_chunks.embedding` 用 `Unsupported("vector")`，schema 不限定维度，实际写入 384 维
- 文档处理完成状态统一为 **`done`**，不是 completed
- SSE 事件既实时推送，也持久化到 `task_events` 表

### ⚠️ 前置条件

本章依赖**用户系统已完成**（第 2.5 章的 RBAC user-system，端口 4002）。chat 服务复用同一套 JWT 鉴权，用相同的 `JWT_SECRET` 校验令牌，从令牌中解析 `userId`，据此隔离不同用户的会话、文档和向量。

另外需要一个**带 pgvector 扩展的 PostgreSQL**（例如 Docker 镜像 `pgvector/pgvector:pg16`）。

### ✅ 本章验收点

- 完成 Prisma Schema：conversations、messages、documents、document_chunks、task_events 五张核心表
- 用 pgvector 替换 MemoryVectorStore，向量持久化到 PostgreSQL
- 文件上传接口，支持 PDF / TXT / MD / DOCX，元数据入库
- 文件解析 → 分块 → 向量化 → 落库的完整 Pipeline
- 会话按用户隔离，历史消息持久化，重启不丢失
- SSE 实时推送向量化任务进度，并持久化任务事件
- 统一链路：登录 → 创建会话 → 上传需求文档 → 带上下文的需求分析 → 结果持久化

---

## 5.1 从 Demo 到生产，还差什么

| 能力 | 第四章实现 | 生产级问题 | 本章方案 |
|---|---|---|---|
| 会话记忆 | `InMemoryChatMessageHistory` | 重启丢失，无用户隔离 | PostgreSQL + Prisma 持久化 |
| 向量存储 | `MemoryVectorStore` | 进程退出即清空，需重新灌库 | pgvector 持久化检索 |
| 业务数据 | `workspace/*.json` 手写文件 | 无法动态新增，无权限控制 | 文件上传 + 数据库元数据 |
| 用户体系 | 无 | 所有人共享同一上下文 | 复用 RBAC 用户系统，JWT 鉴权 |
| 分析制品 | `reports/*.md` 本地文件 | 无法检索，无法关联用户 | 分析结果写入 messages 表，关联会话与用户 |

核心差距归纳为三类：
1. **数据不持久**：内存数据随进程消失
2. **用户不隔离**：没有身份概念，所有请求共享上下文
3. **文件不可管理**：本地文件没有元数据、权限和生命周期

---

## 5.2 系统架构总览

整条链路四个环节：
1. **用户鉴权**：复用 RBAC 用户系统，通过 JWT 识别当前用户
2. **文档管理**：上传 → 解析 → 分块 → 向量化 → 落库，建立用户私有的需求知识库
3. **会话对话**：创建会话 → 发送消息 → 加载历史 → 语义检索 → Multi-Agent 分析 → 结果持久化
4. **统一存储**：会话、消息、文档元数据和向量全部在同一个 PostgreSQL 实例

> 📌 **为什么选 pgvector 而不是独立向量数据库？** 教学项目和中小规模业务中，pgvector 不需要额外引入独立服务。会话、消息、文档元数据和向量统一在 PostgreSQL，事务一致性更容易保证，部署运维成本更低。数据增长到百万级以上，再评估 Qdrant、Milvus 等专用向量库。只要上层检索接口稳定，底层存储可以后续替换。

---

## 5.3 数据库设计：Prisma Schema 全貌

### 🤖 AI 生成代码 Prompt（对应 5.3）

```
在 services/chat 中完成数据库设计与初始化，严格按以下要求执行：

前置：
- 安装依赖：prisma @prisma/client @prisma/adapter-pg pg（Prisma 7）
- 在 prisma.config.ts 中配置 datasource.url = process.env["DATABASE_URL"]（Prisma 7 不再在 schema 内写 url）

1. Prisma Schema 设计（prisma/schema.prisma）：
   - 启用 pgvector：generator 加 previewFeatures = ["postgresqlExtensions"]，datasource 加 extensions = [vector]
   - 不建 User 表：用户系统由 user-system 微服务维护，userId 用裸 String 关联
   - conversations：id, userId, title, createdAt, updatedAt
   - messages：id, conversationId(关联 conversations, onDelete: Cascade), role(MessageRole), content, metadata(Json?), createdAt
   - documents：id, userId, filename, mimeType, size, filePath?, storageType(默认 local), status(默认 pending), chunkCount(默认 0), createdAt
   - document_chunks：id, documentId(关联 documents, onDelete: Cascade), content, chunkIndex, embedding(Unsupported("vector"))
   - task_events：id, userId, taskType, taskId, status(TaskStatus), message?, metadata?, createdAt, readAt?
   - 枚举：MessageRole { USER, ASSISTANT }、TaskStatus { pending, processing, done, error }

2. Prisma Service：
   - 新建 services/chat/src/prisma/prisma.service.ts（用 @prisma/adapter-pg）
   - 新建 services/chat/src/prisma/prisma.module.ts（Global module）

3. 迁移与验证：
   - 执行 bun run db:migrate
   - 执行 bun run db:generate
```

### 5.3.1 整体数据模型

| 表 | 用途 |
|---|---|
| `conversations` | 会话容器，绑定 `userId`。对应第四章的 sessionId，但有了持久化和归属 |
| `messages` | 会话中的每条消息，`role` 区分 USER / ASSISTANT |
| `documents` | 上传文件的元数据，`status` 跟踪处理进度（pending → processing → done / error） |
| `document_chunks` | 文件切分后的文本块，带 `embedding` 向量，用于语义检索 |
| `task_events` | 异步任务事件，既用于 SSE 推送，也作为可查询的任务历史 |

### 5.3.2 Prisma Schema 定义

```prisma
// services/chat/prisma/schema.prisma

generator client {
  provider        = "prisma-client-js"
  previewFeatures = ["postgresqlExtensions"]
}

datasource db {
  provider   = "postgresql"
  extensions = [vector]
}

// 用户表在 user-system 微服务中，这里 userId 用裸 String 关联（不建外键）

model conversations {
  id        String     @id @default(cuid())
  userId    String
  title     String     @default("New Conversation")
  createdAt DateTime   @default(now())
  updatedAt DateTime   @updatedAt
  messages  messages[]

  @@index([userId])
}

model messages {
  id             String        @id @default(cuid())
  conversationId String
  role           MessageRole
  content        String
  metadata       Json?
  createdAt      DateTime      @default(now())
  conversations  conversations @relation(fields: [conversationId], references: [id], onDelete: Cascade)

  @@index([conversationId])
}

model documents {
  id              String            @id @default(cuid())
  userId          String
  filename        String
  mimeType        String
  size            Int
  filePath        String?
  storageType     String            @default("local")
  status          String            @default("pending")
  chunkCount      Int               @default(0)
  createdAt       DateTime          @default(now())
  document_chunks document_chunks[]

  @@index([userId])
}

model document_chunks {
  id         String                 @id @default(cuid())
  documentId String
  content    String
  chunkIndex Int
  embedding  Unsupported("vector")?
  documents  documents              @relation(fields: [documentId], references: [id], onDelete: Cascade)

  @@index([documentId])
}

model task_events {
  id        String     @id @default(cuid())
  userId    String     @db.VarChar(255)
  taskType  String     @db.VarChar(100)
  taskId    String     @db.VarChar(255)
  status    TaskStatus
  message   String?
  metadata  Json?
  createdAt DateTime   @default(now()) @db.Timestamptz(6)
  readAt    DateTime?  @db.Timestamptz(6)

  @@index([taskType])
  @@index([userId, createdAt])
}

enum MessageRole {
  USER
  ASSISTANT
}

enum TaskStatus {
  pending
  processing
  done
  error
}
```

> ⚠️ **关于 vector 维度**：`embedding` 用 `Unsupported("vector")` 不限定维度，实际写入第四章模型输出的 384 维。切换到 1536 维模型时无需改 schema，只要保证写入维度一致（也可以显式写 `vector(384)` 加约束）。

### 5.3.3 关键设计决策

**为什么 messages 用 `onDelete: Cascade`？** 会话被删除时，其下消息同步清除，避免留下没有归属的孤儿数据。`document_chunks` 同理随 `documents` 级联删除。

**为什么 documents 的 status 用字符串而不是枚举？** 文档处理状态可能随业务扩展（如新增 archived），字符串更灵活；`messages.role`、`task_events.status` 取值稳定，用枚举获得更强的类型约束。

**为什么 embedding 是可选的（`?`）？** 分块和向量化是异步的两步操作，chunk 创建时可能还没向量化。检索时用 `embedding IS NOT NULL` 过滤。

### 5.3.4 PrismaService（全局模块）

Prisma 7 使用驱动适配器（`@prisma/adapter-pg`）连接数据库，连接串放在 `prisma.config.ts` 与 PrismaClient 构造中：

```typescript
// services/chat/src/prisma/prisma.service.ts
import { Injectable, OnModuleDestroy, OnModuleInit } from '@nestjs/common';
import { PrismaClient } from '@prisma/client';
import { PrismaPg } from '@prisma/adapter-pg';

@Injectable()
export class PrismaService
  extends PrismaClient
  implements OnModuleInit, OnModuleDestroy
{
  constructor() {
    const adapter = new PrismaPg({
      connectionString: process.env.DATABASE_URL,
    });
    super({ adapter });
  }

  async onModuleInit() {
    await this.$connect();
  }

  async onModuleDestroy() {
    await this.$disconnect();
  }
}
```

```typescript
// services/chat/src/prisma/prisma.module.ts
import { Global, Module } from '@nestjs/common';
import { PrismaService } from './prisma.service';

@Global()
@Module({
  providers: [PrismaService],
  exports: [PrismaService],
})
export class PrismaModule {}
```

### 🧪 验证（对应 5.3）

```bash
cd services/chat
# 确保 PostgreSQL 已启动，且 .env 中配置了 DATABASE_URL
bun run db:migrate
bun run db:generate
bun run db:studio
```

验收标准：Prisma Studio 能打开，五张表结构正确；`document_chunks` 表包含 `embedding` 列（类型 vector）。

---

## 5.4 会话持久化：从 InMemoryHistory 到 PostgreSQL

### 🤖 AI 生成代码 Prompt（对应 5.4）

```
在 services/chat 的 LangChain 层中，用 PostgreSQL 替换 InMemoryChatMessageHistory，严格按以下要求执行：

1. 会话服务（services/chat/src/conversation/conversation.service.ts）：
   - create(userId, title?) / findByUser(userId) / findById(conversationId, userId)（含权限校验）/ delete(conversationId, userId)

2. 消息服务（services/chat/src/message/message.service.ts）：
   - addMessage(conversationId, role, content, metadata?)
   - getHistory(conversationId, limit?)
   - getHistoryAsLangChainMessages(conversationId)：转换为 LangChain BaseMessage 数组

3. 自定义 ChatMessageHistory（services/chat/src/message/db-chat-history.ts）：
   - 继承 BaseListChatMessageHistory，内部调用 MessageService 读写 messages 表
   - 与 RunnableWithMessageHistory 兼容

4. 新增路由（@Controller('api/conversations')，全部经 JwtAuthGuard）：
   - POST /：创建会话
   - GET /：当前用户会话列表
   - GET /:id/messages：会话消息历史
   - POST /:id/chat：在指定会话中发送消息
   - DELETE /:id：删除会话
```

### 5.4.1 变化了什么，不变的是什么

**变化的是存储层**：
- `Map<string, InMemoryChatMessageHistory>` → Prisma 操作 `conversations` + `messages` 表
- sessionId → conversationId（有了真实数据库主键）
- 匿名会话 → 用户绑定会话（通过 userId）

**不变的是调用方式**：`getMessages()` 仍返回 `BaseMessage[]`，`addMessage()` 仍接受 `BaseMessage`，`RunnableWithMessageHistory` 用法完全不变。这正是第四章"上层不依赖具体实现"的工程价值。

### 5.4.2 自定义 DbChatHistory

`BaseListChatMessageHistory` 要求实现 `getMessages()` 和 `addMessage()`，只需把底层从内存换成 Prisma。role 映射：`HumanMessage` → USER，其余 → ASSISTANT。

```typescript
// services/chat/src/message/db-chat-history.ts
import { BaseListChatMessageHistory } from '@langchain/core/chat_history';
import { BaseMessage, HumanMessage } from '@langchain/core/messages';
import { MessageService } from './message.service';
import { MessageRole } from '@prisma/client';

export class DbChatHistory extends BaseListChatMessageHistory {
  lc_namespace = ['chat', 'db'];

  constructor(
    private readonly conversationId: string,
    private readonly messageService: MessageService,
  ) {
    super();
  }

  async getMessages(): Promise<BaseMessage[]> {
    return this.messageService.getHistoryAsLangChainMessages(
      this.conversationId,
    );
  }

  async addMessage(message: BaseMessage): Promise<void> {
    const role =
      message instanceof HumanMessage
        ? MessageRole.USER
        : MessageRole.ASSISTANT;
    await this.messageService.addMessage(
      this.conversationId,
      role,
      typeof message.content === 'string'
        ? message.content
        : JSON.stringify(message.content),
    );
  }

  async addMessages(messages: BaseMessage[]): Promise<void> {
    for (const m of messages) await this.addMessage(m);
  }

  async clear(): Promise<void> {
    await this.messageService.clearHistory(this.conversationId);
  }
}
```

```typescript
// services/chat/src/message/message.service.ts
import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { MessageRole, Prisma } from '@prisma/client';
import { BaseMessage, HumanMessage, AIMessage } from '@langchain/core/messages';

@Injectable()
export class MessageService {
  constructor(private readonly prisma: PrismaService) {}

  async addMessage(
    conversationId: string,
    role: MessageRole,
    content: string,
    metadata?: Record<string, unknown>,
  ) {
    return this.prisma.messages.create({
      data: {
        conversationId,
        role,
        content,
        metadata: metadata as Prisma.InputJsonValue,
      },
    });
  }

  async getHistory(conversationId: string, limit?: number) {
    return this.prisma.messages.findMany({
      where: { conversationId },
      orderBy: { createdAt: 'asc' },
      ...(limit ? { take: limit } : {}),
    });
  }

  async getHistoryAsLangChainMessages(
    conversationId: string,
  ): Promise<BaseMessage[]> {
    const messages = await this.getHistory(conversationId);
    return messages.map((m) =>
      m.role === MessageRole.USER
        ? new HumanMessage(m.content)
        : new AIMessage(m.content),
    );
  }

  async clearHistory(conversationId: string) {
    await this.prisma.messages.deleteMany({ where: { conversationId } });
  }
}
```

### 5.4.3 会话服务：CRUD + 用户隔离

```typescript
// services/chat/src/conversation/conversation.service.ts
import {
  Injectable, NotFoundException, ForbiddenException,
} from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

@Injectable()
export class ConversationService {
  constructor(private readonly prisma: PrismaService) {}

  async create(userId: string, title?: string) {
    return this.prisma.conversations.create({
      data: { userId, title: title ?? 'New Conversation' },
    });
  }

  async findByUser(userId: string) {
    return this.prisma.conversations.findMany({
      where: { userId },
      orderBy: { updatedAt: 'desc' },
    });
  }

  async findById(conversationId: string, userId: string) {
    const conv = await this.prisma.conversations.findUnique({
      where: { id: conversationId },
    });
    if (!conv) throw new NotFoundException('会话不存在');
    if (conv.userId !== userId) {
      throw new ForbiddenException('无权访问该会话');
    }
    return conv;
  }

  async delete(conversationId: string, userId: string) {
    await this.findById(conversationId, userId);
    await this.prisma.conversations.delete({ where: { id: conversationId } });
  }
}
```

JWT 鉴权由 `JwtAuthGuard` + `JwtStrategy` 完成：从 `Authorization: Bearer`、Cookie、query token 三种来源取令牌，校验后把 `userId` 注入 `req.user`（与 user-system 共用同一 `JWT_SECRET`）。

### 🧪 验证（对应 5.4）

```bash
# 创建会话
curl -X POST http://localhost:4001/api/conversations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "需求分析测试"}'

# 在会话中发送消息（RAG + 多 Agent，见 5.9）
curl -X POST http://localhost:4001/api/conversations/$CONV_ID/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"input": "我们要做一个面向需求分析师的会话记忆系统"}'

# 重启服务后验证历史不丢失
curl http://localhost:4001/api/conversations/$CONV_ID/messages \
  -H "Authorization: Bearer $TOKEN"
```

验收标准：重启服务后 `GET /:id/messages` 仍返回完整历史；不同用户无法访问对方的会话（403）。

> 注：课程原文 curl 写的是 `Bearer$TOKEN`（少了空格），已修正。

---

## 5.5 文件上传与存储

### 🤖 AI 生成代码 Prompt（对应 5.5）

```
在 services/chat 中实现文件上传功能，严格按以下要求执行：

1. 安装依赖：@nestjs/platform-express、multer、@types/multer

2. 文件上传服务（services/chat/src/document/document.service.ts）：
   - upload(userId, file, filename)：保存到 uploads/{userId}/{timestamp}-{name}，元数据写入 documents 表（status: pending）
   - findByUser(userId) / findById(documentId, userId)（权限校验）/ delete(documentId, userId)（含物理文件）
   - 允许类型：text/plain, text/markdown, text/x-markdown, application/pdf, docx/msword
   - 文件大小限制：10MB

3. 新增路由（@Controller('api/documents')，经 JwtAuthGuard）：
   - POST /upload（multipart/form-data，内存存储 + fileFilter）
   - POST /:id/process：触发解析+分块+向量化（异步，返回 202）
   - GET / : 文档列表；GET /:id：详情；DELETE /:id
```

第四章的"文件"是预先放在 `workspace/` 的静态样例，用户无法动态新增，也没有归属。本节实现真实上传：用户上传自己的需求文档，系统保存文件、记录元数据，为后续解析与向量化做准备。

### 5.5.1 文件上传服务（节选）

```typescript
async upload(userId: string, file: Express.Multer.File, filename: string) {
  if (!file) throw new BadRequestException('未上传文件');
  if (!ALLOWED_MIME_TYPES.includes(file.mimetype)) {
    throw new BadRequestException(`不支持的文件类型：${file.mimetype}`);
  }

  const dir = path.join('uploads', userId);
  fs.mkdirSync(dir, { recursive: true });

  const savedName = `${Date.now()}-${filename}`;
  const filePath = path.join(dir, savedName);
  fs.writeFileSync(filePath, file.buffer);

  return this.prisma.documents.create({
    data: {
      userId,
      filename,
      mimeType: file.mimetype,
      size: file.size,
      storageType: 'local',
      filePath,
    },
  });
}
```

### 5.5.2 上传路由（节选）

控制器用 `FileInterceptor` + `memoryStorage()`，在 `fileFilter` 拦截非法类型，`limits` 限制 10MB。`POST /:id/process` 异步触发处理，立即返回 202：

```typescript
@Post(':id/process')
@HttpCode(HttpStatus.ACCEPTED)
async process(@Req() req: Request, @Param('id') id: string) {
  const userId = (req.user as any).userId;
  await this.documentService.findById(id, userId);
  this.chunkService.processDocument(id, userId).catch((err) => {
    console.error(`[DocumentProcess] documentId=${id} failed:`, err);
  });
  return { message: '处理已开始', documentId: id };
}
```

### 🧪 验证（对应 5.5）

```bash
curl -X POST http://localhost:4001/api/documents/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@requirement-spec.md;type=text/markdown" \
  -F "filename=requirement-spec.md"

curl http://localhost:4001/api/documents -H "Authorization: Bearer $TOKEN"
```

验收标准：上传成功返回 document 记录，status 为 `pending`；`uploads/{userId}/` 下能找到文件；列表接口返回用户已上传的文件。

---

## 5.6 文件解析与分块策略

### 🤖 AI 生成代码 Prompt（对应 5.6）

```
在 services/chat 中实现文件解析与分块，严格按以下要求执行：

1. 安装依赖：@langchain/textsplitters、pdf-parse、mammoth

2. 文件解析器（services/chat/src/document/parsers/）：
   - text.parser.ts（TXT/MD）、pdf.parser.ts（PDF）、docx.parser.ts（DOCX）
   - parser.factory.ts：extractText(filePath, mimeType) 按 MIME 路由

3. 分块 + 向量化（services/chat/src/document/chunk.service.ts）：
   - RecursiveCharacterTextSplitter（chunkSize: 500, chunkOverlap: 50）
   - processDocument(documentId, userId)：解析 → 分块 → 向量化 → 落库 → 更新 status/chunkCount
```

文件上传后系统拿到的只是静态文件。要基于语义检索，需要先把文件解析为文本，再切分成适合向量化的文本块。

### 5.6.1 文件解析器

不同文件类型用不同解析方式，由工厂按 MIME 路由：

```typescript
// services/chat/src/document/parsers/parser.factory.ts
import { parseText } from './text.parser';
import { parsePdf } from './pdf.parser';
import { parseDocx } from './docx.parser';

export async function extractText(
  filePath: string,
  mimeType: string,
): Promise<string> {
  switch (mimeType) {
    case 'application/pdf':
      return parsePdf(filePath);
    case 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
    case 'application/msword':
      return parseDocx(filePath);
    case 'text/plain':
    case 'text/markdown':
    case 'text/x-markdown':
      return parseText(filePath);
    default:
      return parseText(filePath);
  }
}
```

### 5.6.2 分块 + 落库

```typescript
const splitter = new RecursiveCharacterTextSplitter({
  chunkSize: 500,
  chunkOverlap: 50,
});
const text = await extractText(doc.filePath, doc.mimeType);
const chunks = await splitter.splitText(text);
// 先清空旧分块，再逐条写入 document_chunks
await this.prisma.document_chunks.deleteMany({ where: { documentId } });
```

> 📌 **分块参数**
> - `chunkSize: 500`：每块约 500 字符，适合中文短文档
> - `chunkOverlap: 50`：相邻块重叠 50 字符，避免语义在切分边界处断裂

---

## 5.7 向量化落库：从 MemoryVectorStore 到 pgvector

### 🤖 AI 生成代码 Prompt（对应 5.7）

```
在 services/chat 中实现向量化落库，严格按以下要求执行：

1. 向量化服务（services/chat/src/document/embedding.service.ts）：
   - 复用第四章 @xenova/transformers（Xenova/paraphrase-multilingual-MiniLM-L12-v2）
   - embedTexts(texts)：mean pooling + L2 单位化，返回 384 维向量

2. 完整 Pipeline（chunk.service.ts 的 processDocument）：
   - 解析 → 分块 → embedTexts → 用 raw SQL 写入 document_chunks.embedding（vector）
   - 更新 documents.status 与 chunkCount

3. 语义检索（services/chat/src/document/search.service.ts）：
   - similaritySearch(query, userId, topK)：query 向量化 → pgvector <=> 余弦距离
   - JOIN documents 过滤 userId（用户隔离）→ 返回 topK（content + score）

4. 新增路由：POST /api/search（@Controller('api/search')，经 JwtAuthGuard）
```

### 5.7.1 向量化服务

沿用第四章：`@xenova/transformers` 本地 pipeline，mean pooling + L2 单位化，输出 384 维。

```typescript
async embedTexts(texts: string[]): Promise<number[][]> {
  const embedder = await this.getEmbedder();
  const cleanTexts = texts.map((t) => t.replace(/\n/g, ' '));
  const rawOutput = (await embedder(cleanTexts)) as any;
  const inputs = embedder.tokenizer(cleanTexts, {
    padding: true,
    truncation: true,
  });
  const pooled = mean_pooling(rawOutput, inputs.attention_mask);
  return pooled.normalize(2, -1).tolist(); // 384 维
}
```

> 练习项目第四章已改为 `pipeline(...)(texts, { pooling: 'mean', normalize: true })`，效果相同。

### 5.7.2 完整文档处理 Pipeline

`processDocument` 把解析、分块、向量化、落库串成一条链，并在关键节点推送 SSE（见 5.8）。Prisma 不原生写 vector 类型，用 raw SQL 写入：

```typescript
const text = await extractText(doc.filePath, doc.mimeType);
const chunks = await this.splitter.splitText(text);
await this.prisma.document_chunks.deleteMany({ where: { documentId } });

const vectors = await this.embedding.embedTexts(chunks);
for (let i = 0; i < chunks.length; i++) {
  const created = await this.prisma.document_chunks.create({
    data: { documentId, content: chunks[i], chunkIndex: i },
  });
  const vector = `[${vectors[i].join(',')}]`;
  await this.prisma.$executeRaw`
    UPDATE document_chunks SET embedding = ${vector}::vector
    WHERE id = ${created.id}
  `;
}

await this.prisma.documents.update({
  where: { id: documentId },
  data: { status: 'done', chunkCount: chunks.length },
});
```

### 5.7.3 语义检索服务（带用户隔离）

与第四章最关键的差异：检索结果**只返回当前用户自己上传的文档**（`JOIN documents ... WHERE d."userId" = ...`）。

```typescript
async similaritySearch(
  query: string,
  userId: string,
  topK = 5,
): Promise<SearchResult[]> {
  const [vector] = await this.embedding.embedTexts([query]);
  if (!vector || vector.length === 0) {
    throw new Error('EmbeddingService returned no vector for query');
  }

  // vector 字面量内联为 SQL（无法用 $1::vector 绑定）；userId/topK 仍参数化，安全
  const vecRaw = Prisma.raw(`'[${vector.join(',')}]'::vector`);

  const rows = await this.prisma.$queryRaw<Array<{
    chunk_id: string;
    document_id: string;
    content: string;
    score: string | number;
    chunk_index: number;
  }>>`
    SELECT dc.id AS chunk_id, dc."documentId" AS document_id,
           dc.content AS content, dc."chunkIndex" AS chunk_index,
           1 - (dc.embedding <=> ${vecRaw}) AS score
    FROM document_chunks dc
    JOIN documents d ON d.id = dc."documentId"
    WHERE d."userId" = ${userId} AND dc.embedding IS NOT NULL
    ORDER BY dc.embedding <=> ${vecRaw}
    LIMIT ${topK}
  `;

  return rows.map((r) => ({
    chunkId: r.chunk_id,
    documentId: r.document_id,
    content: r.content,
    score: Number(r.score),
    chunkIndex: r.chunk_index,
  }));
}
```

> ⚠️ **关于 `<=>` 运算符**：pgvector 提供的**余弦距离**，值越小越相似。用 `1 - distance` 转为相似度分数（越大越相似）。pgvector 还支持 `<->`（L2 距离）和 `<#>`（内积）。

### 🧪 验证（对应 5.7）

```bash
# 触发处理（异步返回 202）
curl -X POST http://localhost:4001/api/documents/$DOC_ID/process \
  -H "Authorization: Bearer $TOKEN"

# 语义检索（只命中当前用户文档）
curl -X POST http://localhost:4001/api/search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "怎样判断一个需求是否完整", "topK": 3}'
```

验收标准：处理完成后 `document_chunks.embedding` 不为 NULL，`documents.status` 为 `done`；检索返回相关片段，且只包含当前用户的文档。

---

## 5.8 异步任务通知：SSE 推送机制

### 🤖 AI 生成代码 Prompt（对应 5.8）

```
在 services/chat 中实现 SSE 任务推送机制，严格按以下要求执行：

1. SseService（services/chat/src/sse/sse.service.ts）：
   - 维护 Map<userId, Set<Response>>（一个用户多 Tab 共用）
   - addConnection(userId, res) / removeConnection(userId, res)
   - emit(userId, event)：先持久化到 task_events 表，再实时推送给在线连接
   - 用 @nestjs/schedule 定期清理离线 entry 与 30 天前的 task_events

2. SseController（@Controller('api/sse')，经 JwtAuthGuard）：
   - GET /tasks：text/event-stream，注册连接 + 心跳，断开时清理

3. TaskEventController（@Controller('api/tasks')）：
   - GET /history：分页查询任务历史；GET /:taskId；PATCH /:taskId/read

4. ChunkService.processDocument 在开始/完成/失败时 emit 对应状态事件
```

`POST /api/documents/:id/process` 立即返回 202，实际处理在后台执行，耗时不固定。前端需要感知进度、完成与失败原因，因此引入实时通知。

### 5.8.1 为什么选 SSE 而不是 WebSocket

| 维度 | SSE | WebSocket |
|---|---|---|
| 通信方向 | 服务端 → 客户端（单向） | 双向 |
| 协议 | 标准 HTTP，自动重连 | 独立协议，需手动重连 |
| 复杂度 | 低 | 高，需额外网关配置 |
| 适用场景 | 任务进度、状态通知 | 聊天、实时协作 |

本章场景是服务端向客户端推送任务状态，属于典型单向通知，SSE 足够。

### 5.8.2 SseService：连接管理 + 事件持久化（节选）

一个用户一个 `Set<Response>`（多 Tab 共用），emit 时**先写库再推送**：

```typescript
async emit(userId: string, event: TaskEventPayload): Promise<void> {
  // 1. 持久化到 task_events（失败不影响实时推送）
  try {
    await this.prisma.task_events.create({
      data: {
        id: event.id,
        userId,
        taskType: event.taskType,
        taskId: event.taskId,
        status: event.status,
        message: event.message ?? undefined,
        metadata: (event.metadata as any) ?? undefined,
        createdAt: new Date(event.createdAt),
      },
    });
  } catch (err) {
    console.error('[SseService] failed to persist task event:', err);
  }

  // 2. 实时推送给该用户所有在线 Tab
  const set = this.connections.get(userId);
  if (set) {
    const payload = JSON.stringify(event);
    for (const res of set) {
      res.write(`event: task\ndata: ${payload}\n\n`);
    }
  }
}
```

配合 `@nestjs/schedule`：`@Interval` 定期清理离线 entry，`@Cron` 每天清理 30 天前的 task_events（需在 AppModule 中 `ScheduleModule.forRoot()`）。

### 5.8.3 SseController：SSE 端点（节选）

```typescript
@Get('tasks')
streamTasks(@Req() req: Request, @Res() res: Response) {
  const userId = (req.user as any).userId;
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.setHeader('X-Accel-Buffering', 'no');
  res.write(`event: connected\ndata: ${JSON.stringify({ userId })}\n\n`);

  this.sseService.addConnection(userId, res);
  const heartbeat = setInterval(() => res.write(': heartbeat\n\n'), 30000);
  req.on('close', () => {
    clearInterval(heartbeat);
    this.sseService.removeConnection(userId, res);
  });
}
```

### 5.8.4 接入 ChunkService

`processDocument` 在开始 / 完成 / 失败时 emit 事件（`taskType: 'document_vectorize'`，状态 processing / done / error），前端据此更新进度。事件已落库，离线期间的事件也能通过 `GET /api/tasks/history` 补查。

> 📌 **单实例的局限**：SseService 用内存 Map 维护连接，只在单进程内有效。多实例部署时，推送层可换成 Redis Pub/Sub。事件本身已落库，历史不受影响。

### 🧪 验证（对应 5.8）

```bash
# 终端 1：建立 SSE 连接（保持打开）
curl -N -H "Authorization: Bearer $TOKEN" http://localhost:4001/api/sse/tasks

# 终端 2：触发文档处理
curl -X POST http://localhost:4001/api/documents/$DOC_ID/process \
  -H "Authorization: Bearer $TOKEN"

# 查询任务历史
curl "http://localhost:4001/api/tasks/history" -H "Authorization: Bearer $TOKEN"
```

验收标准：终端 1 先收到 `status: processing`，结束后收到 `status: done`（含 chunkCount）；失败收到 `status: error`；task_events 表能查到这些事件。

---

## 5.9 完整调用链路：从登录到智能分析

### 🤖 AI 生成代码 Prompt（对应 5.9）

```
把前面所有能力整合为统一的分析入口，严格按以下要求执行：

1. 统一分析服务（services/chat/src/llm/advanced-analysis.service.ts）：
   - analyze(userId, conversationId, input)：
     1. DbChatHistory 读取会话历史
     2. SearchService 语义检索当前用户文档（topK=3）
     3. 拼接历史 + 检索上下文 + 当前输入
     4. OrchestratorService.orchestrate(input, retrievedContext) 执行多 Agent 分析
     5. 把用户输入与分析结论写入 messages 表
     6. 返回 report、usedAgents、retrievedDocuments

2. POST /api/conversations/:id/chat 接入该服务（非流式 JSON，第六章再升级流式 UI）
```

### 5.9.1 调用链路

```
用户 ──POST /conversations/:id/chat（Bearer Token）──▶ JWT Guard
  ──userId + conversationId + input──▶ ConversationController
     ① DbChatHistory：读取会话历史（SELECT messages）
     ② SearchService：语义检索（pgvector 余弦距离，按 userId 过滤）
     ③ 历史 + 检索上下文 + 当前输入 ──▶ OrchestratorService
        Multi-Agent：抽取 → 澄清 → 分析 + 风控 → 汇总
     ④ 写入 USER + ASSISTANT message（PostgreSQL）
  ◀── 返回报告 + 引用文档
```

### 5.9.2 统一分析服务（整合版，节选）

```typescript
async analyze(userId: string, conversationId: string, input: string) {
  const history = new DbChatHistory(conversationId, this.messageService);
  const messages = await history.getMessages();

  let retrievedDocs: Awaited<
    ReturnType<SearchService['similaritySearch']>
  > = [];
  try {
    retrievedDocs = await this.searchService.similaritySearch(input, userId, 3);
  } catch {
    // 无文档或检索失败时，继续无文档上下文分析
  }

  const retrievedContext = retrievedDocs.length > 0
    ? retrievedDocs
        .map((d, i) =>
          `[文档片段 ${i + 1}]（相关度：${d.score.toFixed(3)}）\n${d.content}`)
        .join('\n\n')
    : '无相关参考文档';

  const enrichedInput = [
    messages.length
      ? `历史对话：\n${messages
          .map((m) => `${m.getType()}: ${m.content}`)
          .join('\n')}`
      : '',
    `当前输入：${input}`,
  ].filter(Boolean).join('\n\n');

  const result = await this.orchestrator.orchestrate(
    enrichedInput,
    retrievedContext,
  );

  await this.messageService.addMessage(conversationId, MessageRole.USER, input);
  if (result.status !== 'need_clarification') {
    await this.messageService.addMessage(
      conversationId,
      MessageRole.ASSISTANT,
      result.report ?? '分析未完成',
      {
        usedAgents: result.usedAgents,
        retrievedDocuments: retrievedDocs.length,
      },
    );
  }

  return {
    ...result,
    retrievedDocuments: retrievedDocs.map((d) => ({
      documentId: d.documentId,
      content: d.content.slice(0, 200),
      score: d.score,
    })),
  };
}
```

检索到的文档片段作为 `retrievedContext` 注入第四章 summaryAgent 预留的 `{retrievedContext}` 变量——第四章那里还是占位符，本章开始传入真实召回结果。

> 注意：这里 `orchestrate` 多了第二个参数 `retrievedContext`，第四章的编排服务需要相应改造。另外这里把"历史对话 + 当前输入"拼成 `enrichedInput`，解决了第四章 `analyze()` 只写记忆、不读记忆的问题。

### 5.9.3 与第四章的关键差异

| 环节 | 第四章（Mock） | 第五章（生产） |
|---|---|---|
| 会话历史 | `InMemoryChatMessageHistory`（内存 Map） | `DbChatHistory` + PostgreSQL |
| 文档检索 | 手动灌库到 `MemoryVectorStore` | 用户上传 → 自动向量化 → pgvector 检索 |
| 用户隔离 | 无 | JWT 鉴权 + userId 过滤 |
| 结果持久化 | `writeReport('reports/...')` 本地文件 | messages 表（关联会话与用户） |
| 重启后状态 | 全部丢失 | 完整保留 |

### 🧪 验证（对应 5.9 · 完整链路）

```bash
# Step 1: 登录获取 Token（user-system，端口 4002）
curl -X POST http://localhost:4002/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Admin@123456"}'

# Step 2: 上传需求规范文档
curl -X POST http://localhost:4001/api/documents/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@requirement-spec.md;type=text/markdown" \
  -F "filename=requirement-spec.md"

# Step 3: 处理文档（解析 + 分块 + 向量化）
curl -X POST http://localhost:4001/api/documents/$DOC_ID/process \
  -H "Authorization: Bearer $TOKEN"

# Step 4: 创建会话
curl -X POST http://localhost:4001/api/conversations \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"title": "需求分析"}'

# Step 5: 发起分析（带知识库上下文）
curl -X POST http://localhost:4001/api/conversations/$CONV_ID/chat \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"input": "帮我判断这个需求是否完整，并产出一份需求分析报告：开发一个面向需求分析师的会话记忆系统"}'

# Step 6: 重启服务后验证历史保留
curl http://localhost:4001/api/conversations/$CONV_ID/messages \
  -H "Authorization: Bearer $TOKEN"
```

**最终验收标准**：
- ✅ 分析结果包含 `retrievedDocuments`，引用了上传的需求规范文档
- ✅ 信息充分时 `usedAgents` 包含全部 5 个 Agent
- ✅ 重启服务后会话历史完整保留
- ✅ 不同用户之间会话和文档完全隔离
- ✅ 未登录用户（无 Token）返回 401

> 示例项目以需求分析作为入口，后续章节都以需求分析为主线。第六章会在本章 schema 上叠加 artifacts（产物）与 UI 协议，并把非流式 chat 升级为流式输出。

---

## 5.10 本章小结

| 小节 | 做了什么 |
|---|---|
| 5.3 数据库设计 | Prisma 7 + PostgreSQL 建立五张核心表，pgvector 提供向量存储 |
| 5.4 会话持久化 | `DbChatHistory` 替换内存历史，重启不丢失，按用户隔离 |
| 5.5 文件上传 | 真实上传接口，支持 PDF/TXT/MD/DOCX，按用户目录隔离存储 |
| 5.6 解析与分块 | 原始文件 → 可向量化文本块，`RecursiveCharacterTextSplitter` 控制块大小和重叠 |
| 5.7 向量化落库 | pgvector 替换 MemoryVectorStore，检索按用户隔离 |
| 5.8 任务通知 | SSE 实时推送向量化进度，任务事件持久化 |
| 5.9 完整链路 | 登录、会话、文档、检索、Multi-Agent 分析串成端到端链路 |

**下一章**：数据已落库、文件可检索、会话已隔离，但交互仍以 curl 为主。第六章讨论前后端协议、流式响应、结构化 UI 渲染，把 AI 分析结果转化为适合产品的交互体验。

---

## 评论区值得记下的经验

- **本章依赖第 2.5 章的 RBAC 用户系统**：登录拿 JWT 的 user-system（端口 4002）需要先搭好，作者说那一章主要是为了熟悉 Superpowers
- **课程中段突然出现前端页面**，没有给出生成步骤，读者反映很难对齐；作者表示前端不重要，让 AI 写即可
- **`services/api` → `services/chat`**：课程中途因为插入了用户系统，服务名从 api 改成了 chat
- 这几章早期没有对应的仓库分支，作者后续章节才补齐；GitHub 仓库的 commit 和课程内容不完全一致
- 课程 curl 示例里的 `Bearer$TOKEN` 少了空格，照抄会导致鉴权失败
