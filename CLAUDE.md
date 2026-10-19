# Agent 工程课程 · 项目规则

## 2026-10-19 顺序执行纠正（最高优先级）

严格按SCHEDULE-45D.md的D01→D02→D03→…→D32推进。当前单元的教学与约定验收完成后进入下一单元；一天完成后可按顺序继续下一单元。实际日期与单元编号分别记录。教师按面试要求重组原课程的安排已体现在这份计划内；任何进一步跳号或跨单元调整须先得到学生明确同意。当前返回D02收尾；已提前讲的D06工具知识作为已有讲授记录保存，安排到D06再复习验收。用户跳过的独立裁剪练习继续按原约定并入后续综合检查，其余D02收尾集中处理，依据实际证据确认完成。


## 新概念与 API 教学顺序（2026-10-16，优先执行）

每次授课前核对原课程对应小节和学生已掌握前置知识，执行 interview-training/TEACHING-MAP.md。新概念/API首次出现，依次解释：要解决的具体问题、学生熟悉的JS写法、所属对象或导入来源、参数、返回值、实际执行时机、在完整流程中的位置。示例涉及的新变量先定义；概念片段与可运行文件明确区分。学生看过或运行过代码仅作为相应证据，理解与独立实现分别验收。按完整功能组织教学，关键前置当堂补齐，重复的小练习合并到阶段验收。工具调用从原3.8.1讲起，再到3.8.2–3.8.5和4.3；bindTools须在普通函数、工具名称/说明/参数规则之后介绍。


2026-10-16展示约定：业务学习与实作优先使用现有浏览器聊天页面，展示用户输入、工具名称/参数、工具结果与最终回复；PowerShell用于服务启动、必要排错和专项工程检查。避免让学生依靠整段终端对象日志理解业务。概念讲解用流程图与短数据示例，工具接入状态按源码/运行证据分别说明，学生实际结果作为验收依据。

## 2026-10-16最新教学节奏修正（优先执行）

用户明确：面试岗位要求决定教学主线，教师自行设计顺序，用原课程对应内容补齐原理和工程细节。原课程章节顺序作为参考，教学按能力依赖和项目推进重组，全部内容去向继续核对。减少过碎拆分、重复解释、每块重复展示完整表格和大量雷同运行作业；每次讲清一个完整主题，保留必要深度、关键代码、必背完整答案与面试追问。作业集中在有价值的功能、真实失败分支和阶段综合任务，小型API演示可用阅读与口述覆盖。学习进度简短交代当前位置、下一主题和关键缺口，完整表保存在文档。

用户已看腻Excel导入/5000行，后续更换业务案例，优先选知识库问答、工具查订单、客服工单等适合当前主题的场景。当前独立裁剪小练习按用户要求跳过实测，记录已讲解、实操未验收；后续项目或阶段任务合并检查相关能力。学生已有文件和证据保留。45天、深圳15–30k目标、课程覆盖与独立掌握标准继续执行，独立得分依证据更新。

## 当前主线覆盖：45天深圳Agent求职训练 V3

2026-10-16最新用户要求优先执行：2026-10-16至2026-11-29共45个自然日，每周五天、每天四至六小时，按D01–D32验收单元组织。D01已通过，当前同日正式进入D02。单元目标验收通过后直接进入下一单元，统一记录为正式教学；实际日期、单元、时长和待验收分别保存。旧章节安排及历史八周记录供查阅。

开始教学先读AGENTS.md当前主线，以及interview-training/PLAN.md V3、SCHEDULE-45D.md、PROGRESS.md、COURSE-COVERAGE.md和REQUIREMENTS.md。27项课程全部覆盖，100检查点及章节门槛、七项额外材料、岗位实操、排错、安全和两次模拟面试完整保留。每课核对原文全部编号子节并登记去向。采用业务驱动的Agent后端主线，熟悉的前端基础诊断后合并复测；新概念完整讲解。

执行AGENTS.md第16–21条：每次续课与课末给实际日期、当前单元授课/实操完成数、剩余动作、完整通过单元数/32、课程独立分数及距80分和章节门槛缺口。学生提交后直接批改并衔接下一块；亲自作答和运行时等待证据；用户明确下课时保存daily-reviews/YYYY-MM-DD.md，包括完整必背答案、复习题及答案、错题、证据、剩余和下次第一步。复习按+1/+3/+7/+14自然日，到课处理。持续目标草稿见GOAL-PROMPT.md，激活由用户操作。

每个经过验证的学习小目标自动按明确路径提交和普通推送当前分支，报告编号/范围/验证。学生业务代码、运行模型和服务启动按既有教学授权执行；其他改动保留。原课程、平台进度、实现状态、独立掌握分别记录。岗位截图S1–S7和带日期公开样本作为要求依据，具体投递JD逐条核对；学历、真实经验和岗位专项按证据记录。

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
