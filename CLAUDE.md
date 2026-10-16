# Agent 工程课程 · 项目规则

## 当前主线覆盖：八周深圳 Agent 求职训练

2026-10-16新增持续规则：每完成一个经验证的小目标或适合保存的学习阶段，由AI检查相关改动、提交并普通推送现有分支，报告提交编号/范围/验证；遵循AGENTS.md第16条的范围与凭据处理要求。每次课末、批改后和用户询问时，按第17条汇报当日完成/剩余、八周位置、课程独立验收分数及缺口、下步动作与Git结果，更新PROGRESS.md顶部看板。当天任务完成比例、课程掌握分数和实际学习时长分别记录，待测项据实标注。

2026-10-15 最新安排采用 interview-training/PLAN.md V2：深圳 Agent 开发，月薪底线15k、目标15–30k，原课程至少80%掌握。读 COURSE-COVERAGE.md 的100检查点与章节门槛，按V2同时执行岗位实操、面试与课程验收；已有前端基础短诊断，主线进入Agent后端。

用户于 2026-10-15 明确要求从基础重学，以深圳 Agent 招聘要求为验收目标，最长两个月；每周五天，每天四至六小时。用户本科、约五年前端经验，熟悉 JS/Vue，后端基础薄弱。

教学开始前读取同目录 AGENTS.md 的“当前教学主线”，以及 `interview-training/PLAN.md`、`REQUIREMENTS.md`、`PROGRESS.md`。这些训练安排优先于下文旧章节顺序。每课必须有完整通俗讲解、学习目标、必背标准答案、实操作业、面试题答案与评分标准；每周安排独立实操和模拟面试，按证据登记掌握情况。学习者说“下一块”时推进课程，并保留未验收任务和补测安排。

旧课程、历史代码与数据库保留为参考；新练习隔离，默认由学生自己动手和启动服务。AI 持续更新训练文档、题库、错题和进度。截图及公开招聘信息按日期和来源维护能力矩阵；岗位专属技能、学历与真实经验分别核对。

用户已补充要求穿插原课程：按 PLAN.md V2 第 3 节，将原课程对应章节纳入每周求职训练。每课标明原章节，补齐该主题所需基础，复用现有项目做观察和修改，配同一套作业与面试验收；课程时间包含在原八周预算内。平台已学完标记和学生独立掌握分别登记。

本目录是《Agent 工程》课程（共 27 章，Node.js / TypeScript 技术栈）的学习仓库：每章的课程笔记、面试题，以及跟着课程动手的练习代码。

运行环境：Windows + PowerShell，Bun 1.4.2，Node 22。

> ⚠️ 电脑用 nvm-windows 管理多个 Node（22.19.0 / 20.11.1 / 14.21.3），切换是**全局生效**的。本课程练习项目（Nest CLI 12）**必须 Node 22**：启动前先 `nvm current` 确认，不是 22 就 `nvm use 22.19.0`。Node 14 下启动会报 `SyntaxError: Unexpected token 'with'`。

---

## 一、目录结构

```
agent-course/
├─ CLAUDE.md                      ← 本文件，整个课程的规则
├─ chapter-01-模型调用/
├─ chapter-02-工程底座/
│  └─ llm/                        ← 练习项目（第二章起所有章节的代码都在这里）
├─ chapter-02.5-AI参与开发/
├─ chapter-03-LangChain起手/
└─ chapter-12-MCP/
   └─ code/                       ← 早期 MCP Server 练习代码（第十二章待重学）
```

每个章节文件夹固定包含：

| 文件 | 内容 |
|---|---|
| `course.md` | 课程原文精简版：去掉图片、推广、评论、重复目录；保留结构、讲解和全部代码；网页丢失的缩进要修正；可补充对照表和评论区经验 |
| `interview-qa.md` | 本章面试题 + 参考答案，按"结论 → 原因 → 例子"组织 |

新章节文件夹命名：`chapter-XX-简短中文名`。

---

## 二、学习与讲课流程

1. **进新章节前**：先回顾上一章核心内容，出 1–2 道回顾题；用户说"正式开始"才讲新章节
2. **拿到章节原文后**：先整理出 `course.md`
3. **一块一块讲**：每块用大白话 + 类比讲清楚，联系前面章节和用户实际踩过的坑，最后出 2–3 道面试风格的题
4. **"下一块" / "下一步" 优先级最高**：用户说了就直接进入下一块，即使题目没答
5. **用户没答题就说"下一块"时，下一块内容的最上方先给出上一块全部题目的参考答案**，再开始新内容
6. 章节讲完，整理出 `interview-qa.md`

### 答题与点评
- 引导用户按 **结论 → 原因 → 例子** 作答
- 如实点评：答到"旁边的问题"、只说关键词没说原因、概念用错，都要直接指出，并给出参考答案

### 动手步骤的写法（必须遵守）
- **每一步完整、自包含**，写清楚：这一步学什么、对应课程哪个概念 → **在哪个目录执行** → **完整文件路径** → **完整文件内容** → 逐段讲解 → 怎么验证
- **禁止**只给片段、禁止写"完整版见 course.md"
- **禁止**只贴代码不讲解，这是课程
- 代码要适配练习项目的实际情况（ESM、`.js` 后缀、已安装的库版本），给代码前先对照 `node_modules` 确认 API
- 所有会弹出的交互选项，提前一次性列出该选什么
- 对话里代码每行尽量短，长行拆开，避免左右滚动
- 动手内容多时拆成几块，每块结尾有可执行的验证和题目

---

## 三、练习项目 `chapter-02-工程底座/llm` 规则

### 结构与端口

| 目录 | 包名 | 端口 |
|---|---|---|
| `packages/contracts` | `@autix/contracts` | — |
| `services/chat`（NestJS 12） | `@autix/chat` | 4001 |
| `clients/chat-web`（Next 16） | `@autix/chat-web` | 3002 |
| `infra/compose` | Docker Compose 配置 | — |

- 前端页面在 `clients/chat-web/src/app/`（有 `src` 目录，不是课程写的 `app/`）
- 后端 LangChain 代码在 `services/chat/src/llm/`

### 命令在哪执行

- **所有 `bun` 命令默认在 `llm` 目录执行**
- 启动后端 `bun run dev:chat`；前端 `bun run dev:chat-web`；一起启动 `bun run dev`
- 给子项目装包：在 `llm` 目录执行 `bun add <包名> --cwd services/chat`，不要不带 `--cwd` 装到根目录
- 只用 Bun。lock 文件只保留 `llm/bun.lock`，子目录不允许有其他 lock 文件
- 子项目里不允许有嵌套的 `.git`

### ESM 规则（`services/chat` 是 `"type": "module"`）

- 相对路径 import 必须写 `.js` 后缀：`from './llm.service.js'`
- 没有 `exports` 字段的包，子路径也要写 `.js`：`from 'supertest/types.js'`
- 装饰器参数里用到的纯类型必须 `import type`：`import type { Response } from 'express'`
- 课程代码按旧版 CommonJS 写，照抄时以项目脚手架的风格为准

### 配置分层

| 内容 | 位置 |
|---|---|
| API Key、服务地址 | `services/chat/.env`（已被 `.gitignore` 忽略，禁止提交） |
| 模型参数、功能开关 | `services/chat/config/langchain.yaml`（**不在 src 里**） |
| 提示词文字 | `services/chat/src/llm/prompts/` |
| 配置加载代码 | `services/chat/src/config/load-langchain-config.ts` |

- YAML 按 `process.cwd()/config/langchain.yaml` 读取，必须以 `services/chat` 为工作目录启动（在 `llm` 目录运行 `bun run dev:chat` 即满足）
- `.env` 由 `src/load-env.ts` 加载，它必须是 `main.ts` 的**第一个 import**，保证其他模块导入时就能读到环境变量
- **当前模型服务：Amux（OpenAI 兼容接口），模型 `gpt-5.6-sol`**。`OPENAI_BASE_URL` 必须带 `/v1`（`https://api.amux.ai/v1`），不带会报 `rsp is not an Object`。实测单次调用 6–30 秒不等
- 换模型后，下面针对旧模型的实测结论要重新验证（结构化输出方式、工具调用、回复长度）
- 以下为旧模型通义千问 `qwen3.8-flash`（思考模式）的实测记录：
- 实测：思考模式下每次调用约 10–20 秒，回复普遍很长
- 实测：`trimMessages` 用 `tokenCounter: model` 时按 OpenAI 分词算，中文约 2.4 token/字，严重高估；`strategy: 'last'` 遇到最后一条就超预算时会**一条都不留**，导致多轮对话失忆。**改用按条数裁剪**：`tokenCounter: (msgs) => msgs.length` + `maxTokens: 10` + `startOn: 'human'`
- 实测：`withStructuredOutput` 不指定 `method` 时默认走 `jsonSchema`，**可用**；指定 `method: 'functionCalling'` 会报 400（思考模式不支持强制 `tool_choice`），不要用

### 本地嵌入模型（第四章起）

- 模型 `Xenova/paraphrase-multilingual-MiniLM-L12-v2`（384 维）**已手动下载到 `services/chat/models/`**（约 135MB，已在 `.gitignore` 里）
- 国内网络从 Hugging Face 自动下载大文件会中途卡住报 `UND_ERR_BODY_TIMEOUT`；`hf-mirror.com` 实测也不稳定。所以代码里设置 `env.localModelPath = <cwd>/models` + `env.allowRemoteModels = false`，只读本地
- 重新下载时用 curl 断点续传（`-C -`），需要 4 个文件：`config.json`、`tokenizer.json`、`tokenizer_config.json`、`onnx/model_quantized.onnx`
- 向量库目前是 `MemoryVectorStore`，**重启后端数据就没了**，要重新灌库

### 代码约定

- 创建模型一律用 `createChatModel()`，禁止在 Service 里直接 `new ChatOpenAI()`
- Prompt 不写死在 Service 方法里，放 `prompts/`，通过 `ChatPromptTemplate` 使用
- 模型调用逻辑写在 Service，Controller 只负责接收请求和返回
- 取模型回复文字用 `.text`，不用 `.content.toString()`
- 新 Module 必须加到 `app.module.ts` 的 `imports`

### 运行与调试

- 一个端口同一时间只能有一个服务，启动前确认旧进程已停止，否则报 `EADDRINUSE`
- `nest start --watch` 只在 `.ts` 变化时自动重启；改 YAML、`.env` 要手动重启
- 启动成功标志：日志出现 `Mapped {...} route` 和 `Chat running on :4001`
- 类型检查（`services/chat` 下 `bun run typecheck`）只检查代码，不检查运行时读取的文件是否存在

### 测试（vitest，在 `services/chat` 目录执行，根目录没有 test 脚本）

- 单元测试 `bun run test`（`**/*.spec.ts`）；e2e `bun run test:e2e`（`**/*.e2e-spec.ts`）
- 真实调用模型的测试默认跳过，需要时 `$env:RUN_LLM_E2E = '1'` 后再跑，跑完 `Remove-Item Env:RUN_LLM_E2E`
- 测试不经过 `main.ts`，需要 API Key 的测试文件第一行要 `import '../src/load-env.js'`
- 单元测试里用不到模型的依赖用 mock（`useValue: { extract: vi.fn() }`），不要真的创建模型
- 模型输出的测试只断言结构和关键语义，不锁死具体措辞

### 接口测试

- **首选 Postman / Apifox 等接口工具**。讲课给测试步骤时，给出：方法、完整地址、Body（JSON），不要只给命令行
- 当前流式接口直接写原始文字，不是标准 SSE（没有 `data:` 前缀），接口工具里通常等生成完一次性显示，属正常
- 本章接口建议保存为一个集合，改代码后回归测试

### Windows / PowerShell

- 没有 `lsof`；`curl` 是别名，要用 `curl.exe`
- 不用接口工具时，发带中文的 JSON 请求要转 UTF-8 字节，**每行单独执行**，不要用反引号多行续行：

```powershell
$body = '{"input":"用户注册时必须绑定手机号，密码至少8位"}'
$bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
$url = 'http://localhost:4001/api/langchain/invoke'
Invoke-RestMethod $url -Method Post -Body $bytes -ContentType 'application/json'
```

- Git Bash 里用 curl 直接发中文会乱码，模型会收到乱码输入

### 已知问题

- 第二章 2.8 的 Docker Compose 配置有多处跑不通，尚未实际运行
