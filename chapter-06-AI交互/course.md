# 第六章：让 AI 做更懂你的交互

## 课程基准

- 官方分支：<https://github.com/Cookieboty/autix-demo/tree/feat/ai-ui>
- 官方分支核对提交：`40da7cc8729ac9e7ec2b47f5820dc73dd46b0863`
- 课程主线：模型输出结构化 UI 协议，前端按 `type` 渲染组件，用户操作以 `UIAction` 回传，状态机推进下一阶段。
- 当前官方分支真实落地范围：6.2 UI 协议、6.3 确定性状态机、6.4 前端组件渲染。
- 6.5 的 Streaming 是生产演进方案，官方 `feat/ai-ui` 分支尚未落地。

## 本章验收点

1. 理解 AI 驱动 UI：模型或业务服务输出结构化 JSON，前端按协议渲染组件。
2. 设计可扩展的 `UIResponse` 联合类型。
3. 用 Zod 和 `withStructuredOutput` 约束模型输出。
4. 用确定性状态机完成 selection → form → confirmation → result。
5. 用 `ComponentRenderer` 把协议映射为 React 组件。
6. 完成用户输入 → UI 指令 → 页面渲染 → UIAction 回传 → 下一阶段的闭环。
7. 理解协议版本、未知组件降级、业务后处理和流式适配。

## 6.1 纯文本回复的天花板

纯 Markdown 能承载解释和报告，但它缺少确定的交互语义。用户需要自行阅读和输入下一步，前端也无法稳定提取“选项、字段、按钮和进度”。

AI 驱动 UI 把回复拆成两层：

```text
message：给用户阅读的说明
components：给前端渲染的 UI 指令
```

例如，模型返回 `selection`：

```json
{
  "message": "请选择分析维度",
  "components": [
    {
      "type": "selection",
      "title": "请选择分析维度",
      "options": [
        {
          "id": "completeness_check",
          "label": "完整性检查",
          "description": "检查必要场景和边界条件"
        },
        {
          "id": "conflict_detection",
          "label": "冲突检测",
          "description": "检查功能与数据一致性冲突"
        }
      ],
      "allowMultiple": false
    }
  ]
}
```

用户点击后回传确定的数据：

```json
{
  "componentType": "selection",
  "payload": {
    "type": "select",
    "selectedId": "completeness_check"
  }
}
```

## 6.2 UI 响应协议与 Structured Output

### 6.2.1 设计原则

- `type` 是组件判别字段，前端只根据它分发组件。
- 每个组件包含完整渲染信息。
- 用户操作统一转成 `UIAction`。
- 一次响应允许组合多个组件。
- 新增组件类型时保留已有类型行为。

### 6.2.2 组件类型

| type | 用途 | 典型操作 |
|---|---|---|
| `text` | Markdown 或普通说明 | 展示 |
| `selection` | 单选或多选卡片 | 回传 `selectedId` |
| `form` | 动态表单 | 回传 `formData` |
| `confirmation` | 重要操作确认 | 回传 `confirmed` |
| `card` | 结构化详情 | 可附带动作按钮 |
| `steps` | 流程进度 | 展示 |
| `table` | 批量结构化数据 | 可回传行号 |
| `action_buttons` | 快捷动作入口 | 回传 `actionId` |

### 6.2.3 核心 TypeScript 协议

后端文件：`services/chat/src/llm/ui-protocol/ui-types.ts`

```ts
export interface SelectionResponse {
  type: 'selection';
  title: string;
  description?: string;
  options: Array<{
    id: string;
    label: string;
    description?: string;
    icon?: string;
    disabled?: boolean;
  }>;
  allowMultiple?: boolean;
}

export interface FormResponse {
  type: 'form';
  title: string;
  description?: string;
  fields: Array<{
    name: string;
    label: string;
    type: 'input' | 'textarea' | 'select' | 'date' | 'number';
    required?: boolean;
    placeholder?: string;
    options?: Array<{ value: string; label: string }>;
  }>;
  submitLabel?: string;
}

export type UIResponse =
  | TextResponse
  | SelectionResponse
  | FormResponse
  | ConfirmationResponse
  | CardResponse
  | StepsResponse
  | TableResponse
  | ActionButtonsResponse;

export interface AIUIResponse {
  message: string;
  components: UIResponse[];
  context?: {
    sessionStage?: string;
    collectedData?: Record<string, unknown>;
  };
}

export interface UIAction {
  componentType: UIResponse['type'];
  payload:
    | { type: 'select'; selectedId: string | string[] }
    | { type: 'submit'; formData: Record<string, unknown> }
    | { type: 'confirm'; confirmed: boolean }
    | { type: 'click'; actionId: string }
    | { type: 'row_select'; rowIndex: number };
}
```

### 6.2.4 Zod Schema

后端文件：`services/chat/src/llm/ui-protocol/ui-schemas.ts`

每种组件都有对应的 `z.object`，并通过判别联合组成统一协议：

```ts
export const uiComponentSchema = z.discriminatedUnion('type', [
  textResponseSchema,
  selectionResponseSchema,
  formResponseSchema,
  confirmationResponseSchema,
  cardResponseSchema,
  stepsResponseSchema,
  tableResponseSchema,
  actionButtonsResponseSchema,
]);

export const aiUIResponseSchema = z.object({
  message: z.string(),
  components: z.array(uiComponentSchema),
  context: z
    .object({
      sessionStage: z.string().nullable().optional(),
      collectedData: z.record(z.unknown()).nullable().optional(),
    })
    .nullable()
    .optional(),
});
```

`z.discriminatedUnion('type', ...)` 会先读取 `type`，再使用对应组件 Schema 校验，错误定位清晰，也与前端组件分发一致。

### 6.2.5 Structured Output

后端文件：`services/chat/src/llm/ui-protocol/ui-response.service.ts`

```ts
private model = createChatModel();
private structuredModel =
  this.model.withStructuredOutput(
    aiUIResponseSchema,
    { method: 'jsonMode' },
  );

private prompt = ChatPromptTemplate.fromMessages([
  ['system', UI_SYSTEM_PROMPT],
  new MessagesPlaceholder('history'),
  ['human', '{input}'],
]);

private chain = this.prompt.pipe(this.structuredModel);
```

当前协议包含 `table.rows` 和 `context.collectedData` 这样的开放字典。当前 OpenAI SDK 的 strict JSON Schema 转换不接受 `z.record(...)`，因此本地 `generate` 使用 `jsonMode` 取得 JSON，再用 Zod 在服务端校验结构。System Prompt 指导模型选择组件。数据真实性仍由数据库、可信服务和业务校验保证。

本地 `@langchain/openai` 的 `withStructuredOutput` 内部调用 `withConfig()`。原版 `withConfig()` 会重新构造基础 `ChatOpenAI`，让 `gpt-5.6-sol` 自动切到当前网关不支持的 Responses API；`model.factory.ts` 覆盖该方法，使配置后的模型继续使用 Chat Completions。

本节接口：

```text
POST /api/ui-chat/generate
```

`generate` 调用模型。模型服务或 Schema 解析失败时，控制器降级到确定性 `UIFlowService`，保持返回结构合法。

## 6.3 完整交互闭环

### 6.3.1 四阶段状态机

```text
select_type
  selection：选择需求类型
      ↓
fill_detail
  form：填写需求详情
      ↓
confirm
  confirmation：确认或返回修改
      ↓
result
  steps + card + action_buttons
```

状态保存在：

```ts
interface SessionContext {
  stage: string;
  collectedData: Record<string, unknown>;
}

private sessions = new Map<string, SessionContext>();
```

该 Map 属于教学版内存状态。服务重启会清空，多实例之间也无法共享。生产实现应迁移到数据库或 Redis。

### 6.3.2 状态推进

```ts
handleAction(sessionId: string, action: UIAction): AIUIResponse {
  const ctx = this.getContext(sessionId);

  switch (ctx.stage) {
    case 'select_type':
      return this.onTypeSelected(ctx, action);
    case 'fill_detail':
      return this.onFormSubmitted(ctx, action);
    case 'confirm':
      return this.onConfirmation(ctx, action);
    default:
      return this.handleButtonAction(ctx, action);
  }
}
```

这里的关键取舍是：模型适合识别开放意图，状态机适合控制重要业务流程。选择、表单提交和确认已经是结构化操作，可以直接确定下一状态。

### 6.3.3 路由

```text
POST /api/ui-chat/chat
  body: { sessionId, input }
  作用：处理自然语言入口，进入相应流程

POST /api/ui-chat/action
  body: { sessionId, action }
  作用：处理 UIAction，推进状态机

POST /api/ui-chat/generate
  body: { input, context? }
  作用：调用 withStructuredOutput，让模型生成 UI 协议
```

## 6.4 前端组件渲染层

### 6.4.1 文件结构

```text
clients/chat-web/src/
├─ app/
│  ├─ page.tsx
│  └─ globals.css
├─ components/ai-ui/
│  ├─ AIChatContainer.tsx
│  ├─ ComponentRenderer.tsx
│  ├─ SelectionCard.tsx
│  ├─ DynamicForm.tsx
│  ├─ ConfirmationDialog.tsx
│  ├─ InfoCard.tsx
│  ├─ StepsProgress.tsx
│  ├─ DataTable.tsx
│  └─ ActionButtons.tsx
└─ types/
   └─ ui-types.ts
```

官方分支采用 `clients/chat-web/app` 和根级 `components`。本地项目采用 `src/app`，因此第六章统一把页面、组件和类型放在 `src` 中，并继续使用 `@/* → ./src/*`。

### 6.4.2 ComponentRenderer

`ComponentRenderer` 使用 `component.type` 做穷尽分发：

```ts
switch (component.type) {
  case 'selection':
    return <SelectionCard ... />;
  case 'form':
    return <DynamicForm ... />;
  case 'confirmation':
    return <ConfirmationDialog ... />;
  case 'card':
    return <InfoCard ... />;
  case 'steps':
    return <StepsProgress ... />;
  case 'table':
    return <DataTable ... />;
  case 'action_buttons':
    return <ActionButtons ... />;
  default:
    return <div>[不支持的组件类型]</div>;
}
```

每个交互组件只收集本地输入，并通过统一的 `onAction(UIAction)` 回传。跨轮状态由容器和后端管理。

### 6.4.3 AIChatContainer

```text
用户输入
→ POST /api/ui-chat/chat
→ 收到 AIUIResponse
→ 显示 message
→ ComponentRenderer 渲染 components
→ 用户点击或提交
→ POST /api/ui-chat/action
→ 渲染下一阶段
```

官方分支通过全局 `ResponseInterceptor` 返回 `{ data: AIUIResponse }`。本地 chat 服务当前直接返回 `AIUIResponse`，本地前端应直接读取响应对象，避免照搬 `payload.data`。

## 6.5 工程化要点与生产建议

### 6.5.1 协议版本

在响应顶层加入版本：

```ts
interface AIUIResponse {
  version: '1.0';
  message: string;
  components: UIResponse[];
}
```

版本用于字段升级、组件新增和多端兼容。

### 6.5.2 未知组件 Fallback

前端 `default` 分支应显示降级提示并记录告警，其他组件继续渲染。

### 6.5.3 后处理校验

Zod 校验结构，业务后处理负责：

- 补齐空 `message`。
- 丢弃空 selection 和空 form。
- 限制单次组件数量。
- 校验按钮权限和业务状态。
- 从可信数据源读取事实字段。

### 6.5.4 text streaming + component batching

```text
Markdown：逐 Token 推送
UI 组件：完整 JSON 整包推送
进度：独立 progress 事件
完成：done 事件后统一持久化
```

推荐流式信封：

```ts
interface StreamMessage {
  messageType:
    | 'markdown'
    | 'ui'
    | 'meta'
    | 'progress'
    | 'done'
    | 'error';
  timestamp: string;
  payload: unknown;
}
```

JSON Agent 静默收集完整输出；Markdown Agent 可以逐 Token 展示；UI 组件需要完整字段后再渲染；最终内容完成后一次性写入数据库。

本节属于生产演进参考，本章本地实现范围与官方分支保持在非流式 UI 状态机。

## 6.6 本章小结

本章把 AI 输出从文本升级为前后端共享的交互协议：

1. `UIResponse` 描述页面展示什么。
2. `UIAction` 描述用户做了什么。
3. Zod 和 Structured Output 保证数据结构可解析。
4. 状态机保证关键流程稳定推进。
5. `ComponentRenderer` 把协议映射为真实 React 组件。
6. 生产环境再补协议版本、可信数据、权限校验、持久化和流式体验。

下一章进入 Agent 的路由、执行与优化决策。

## 本地适配清单

| 项目 | 官方 `feat/ai-ui` | 本地实现要求 |
|---|---|---|
| NestJS | 11 | 12 |
| 后端模块 | CommonJS 风格相对导入 | ESM 相对导入带 `.js` |
| Next 目录 | `app/`、`components/`、`types/` | `src/app/`、`src/components/`、`src/types/` |
| API 响应 | 全局包装为 `{ data }` | 当前直接返回业务对象 |
| 模型访问 | 直接访问服务 | 保留 `createChatModel()` 和可选代理 |
| 6.5 Streaming | 文档参考 | 暂不写入当前业务代码 |
