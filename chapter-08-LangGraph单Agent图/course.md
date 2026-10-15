# 第八章：LangGraph 单 Agent 图实战

## 本章目标与验收

本章承接第六章的需求分析业务和第七章的路由、执行、优化三层决策。学习顺序是固定流程图化 → 入口分类 → 分析工具循环 → 报告质量循环 → 与业务会话及前端进度接合。完成后应能给一条真实输入画出实际节点路径，指出每个节点写入的 State 字段，并说明循环的退出条件和服务返回值来源。

本地项目的第六章 UI 演示仍是独立流程；图化分析与 UI 接合属于后续集成工作。每个阶段以本地实际行为和可运行结果为验收依据。

## 课程与本地项目对齐

- 课程参考分支：<https://github.com/Cookieboty/autix-demo/tree/feat/LangGraph>，核对时分支提交为 `7be4247e91fade55296ed97622cb137aba9e8135`。
- 本地代码目录：`chapter-02-工程底座/llm/`；chat 服务目录：`chapter-02-工程底座/llm/services/chat/`。
- 本地五阶段编排入口：`services/chat/src/llm/agents/orchestrator.service.ts`。当前路径为提取 → 澄清 → 分析与风险并行 → 汇总；信息不足时在澄清后提前返回。
- 本地 `services/chat/package.json` 已安装 `@langchain/langgraph@1.4.15`，8.3 的图文件与 `orchestrator.service.ts` 已接入并通过类型检查、构建；学习者已通过 Apifox 验证真实分析请求。本章教学从 8.1 重新开始；8.4 的路由代码尚未复制到业务文件。
- 本地第六章的 `/api/ui-chat/chat` 和 `/action` 是独立的确定性 UI 流程，界面中的“待分析”表示尚未接入真实五阶段分析。
- 课程分支的图文件包含后续章节代码和调试片段。学习时以逐块迁移为准，不整文件复制。
- 本地 chat 使用 NestJS 12、ESM；新增相对路径 import 保留 `.js` 后缀。

## 学习顺序

| 块 | 本块要回答的问题 | 具体产物 |
| --- | --- | --- |
| 8.1 | LangChain 与 LangGraph 各管什么？本地为什么需要图？ | 对现有执行路径的准确描述 |
| 8.2 | State、Node、Edge、条件边、回边分别负责什么？ | 能手绘最小图并追踪状态 |
| 8.3 | 如何把已有五阶段流程迁入图？ | 可复制的完整文件与本地验证 |
| 8.4 | 如何把分析、查询、闲聊分流？ | classifier 与条件边 |
| 8.5 | 如何让分析节点按需调工具？ | 有上限的 ReAct 子图 |
| 8.6 | 如何检查并局部修订报告？ | 有上限的 Critic-Refine 子图 |
| 8.7–8.8 | 如何接入持久化、进度、人工确认并排障？ | 与本地 NestJS/数据库/UI 的接入与验收 |

## 8.1 从 LangChain 到 LangGraph

### 本块的学习目标

| 层次 | 学完 8.1 应达到的具体结果 |
| --- | --- |
| 必背 | 能说出 LangChain 负责提示词、模型、工具与解析等单步能力的组合；LangGraph 负责多个步骤之间的状态、分支与循环。能说出需求分析原有五阶段顺序。 |
| 至少会讲会用 | 给出“分析需求”“查询状态”“你好”三种输入，能解释为什么需要先选路径；能指出现有五个 Agent 继续由 LangChain 定义，图负责决定哪些 Agent 在何时运行。 |
| 了解 | 知道本章后续依次添加路由、ReAct 工具循环、Critic-Refine 报告修订；知道 Checkpointer 与业务会话消息各保存什么。 |

### 8.1.1 LangChain 在当前项目里做了什么

LangChain 提供调用模型所需的零件：`ChatModel` 把请求发给模型，`ChatPromptTemplate` 组织提示词，`Tool` 描述可调用动作，解析器把模型输出变为应用能消费的数据，`Runnable.pipe()` 连接这些零件。本地 `sub-agents.ts` 中的 `extractAgent = extractPrompt.pipe(model).pipe(parser)` 就是一条调用链：把输入填进提取提示词 → 调用模型 → 得到字符串。其余四个 Agent 也沿用这一模式。固定、短小、一次走完的处理任务很适合这种写法。[官方概览](https://docs.langchain.com/oss/javascript/langgraph/overview)

### 8.1.2 8.3 迁移前的编排怎样处理控制流

在 8.3 迁移前，本地 `OrchestratorService.orchestrate()` 直接决定五个 Agent 何时执行：先提取、再澄清；有澄清问题就返回；信息充分时通过 `Promise.all` 并行调用分析与风险 Agent，最后把两份结果交给汇总 Agent。节点内部的判断由模型完成；提前返回、并行和先后关系写在服务代码里。当前本地代码已经将这段顺序移入 `requirement-analysis-graph.ts`，本节从旧流程出发理解迁移理由。

用户现在可能发送三类输入：“分析批量导入需求”“查询 REQ-001 当前状态”“你好”。现有编排入口主要服务需求分析。扩充后，分类结果应决定目标路径；分析期间查到新证据时可能再次调用工具；报告缺章节时可能重新评审。普通 TypeScript 同样能表达这些控制流，但分支、循环计数、中间状态和进度事件都要由业务代码自行维护，流程增长时更难追踪。[官方图设计教程](https://docs.langchain.com/oss/javascript/langgraph/thinking-in-langgraph)

### 8.1.3 LangGraph 补上的执行层

LangGraph 把流程写成有状态的图。State 统一保存节点间共享的数据；Node 调用已有 Agent、数据库或工具；Edge 表达固定顺序；条件边读取 State 选择下一节点；回边让局部步骤再次执行。编译后的图还有按节点产生事件、图级快照和人工暂停恢复等运行时能力。图节点继续调用 LangChain 组件，两套能力会在同一条请求中协作。[官方概览](https://docs.langchain.com/oss/javascript/langgraph/overview)

| 能力 | 使用现有 LangChain 组件与普通编排时 | 使用 LangGraph 时 |
| --- | --- | --- |
| 线性模型调用 | `prompt.pipe(model).pipe(parser)` 直接组合 | 节点内部沿用同一调用链 |
| 运行时分流 | 在编排服务中维护条件分支 | classifier 写状态，条件边选目标节点 |
| 重复调用工具 | 在服务中维护循环与轮次 | agent/tools 回边，State 保存轮次和结果 |
| 报告质量复查 | 服务调用 critic 并自行安排重试 | critic/refine 子图表达循环与退出 |
| 断点与人工确认 | 业务代码管理中间状态和恢复位置 | Checkpointer 配合中断与恢复 |
| 展示执行进度 | 服务逐阶段手动发事件 | 图按实际执行节点产生更新事件 |

表中“使用 LangGraph”表示它提供这些控制流原语，并不代表安装依赖就自动得到业务逻辑。开发者仍要定义字段、节点、分支规则、工具权限和退出条件。

| 需求 | 当前入口的实现位置 | 图里的表达 |
| --- | --- | --- |
| 提取后做澄清 | 连续 `await` | `extract → clarify` 固定边 |
| 信息不足就结束 | `if` 提前返回 | `clarify` 后的条件边通向 `END` |
| 分析与风险并行 | `Promise.all` | 两个分支写入各自字段，再汇入 summary |
| 分析/查询/闲聊分流 | 需要新增分派逻辑 | classifier 节点写 `intent`，条件边选路径 |
| 按证据多次查工具 | 需要新增循环与计数 | agent/tools 回边加轮次上限 |
| 检查并修订报告 | 需要新增评审逻辑 | critic/refine 回边加修订上限 |

### 8.1.4 这章为什么迁移现有链路

选型时看任务是否需要明确的运行时路径和状态。短 RAG 问答、结构化提取等稳定调用可继续使用 LangChain 链；多路径、循环、图级恢复、人工中断和节点级进度适合放进 LangGraph。课程第八章先迁移现有五段式流程，再逐次添加路由、ReAct 和质量闭环。这样每一步都能与旧结果对照，问题也容易定位。本地第五章的 PostgreSQL 消息表继续保存用户对话；图级 Checkpointer 是否加入，由 8.7 的恢复需求决定。

把“批量导入 Excel，最多一万行，失败数据要能导出”作为贯穿输入：当前服务先得到原始提取文本，再由澄清 Agent 判断信息是否足够；信息充分时并行拿到功能/复杂度分析与风险分析，最后生成报告。8.3 只把这些步骤放进 StateGraph，验收是同一输入仍得到同类报告。8.4 才在入口加 classifier，使“查询 REQ-001 的状态”走查询路径、“你好”走闲聊路径。8.5 让分析步骤依据工具结果继续判断，8.6 给报告加检查与局部修订。这条演进顺序使每次改动都只有一个主要学习目标。

此时要能自己说明采用图的理由：本项目需要观察“运行到了哪个步骤”“为何走这条路径”“循环何时结束”“中间结果怎样交给下一步”。若只把已有五个 `await` 包进图而没有后续路径需求，收益主要是得到统一的状态与扩展位置。后续章节才逐步兑现路由、循环、质检和运行时能力。

### 本块检查

面对“分析 REQ-001”“查询 REQ-001 的状态”“你好”三个输入，能指出：现有五阶段分析入口在哪里；新增的 classifier 应写出什么状态；条件边如何分配三个路径。8.1 只建立系统地图，不改服务代码、不启动服务。

**8.1 必背标准答案：**LangChain 负责单个步骤内部的模型能力，例如把提取提示词、模型和结果解析连成一条链。LangGraph 负责多个步骤之间的执行路径和共享状态，例如提取之后进入澄清、澄清后按结果结束或进入分析。本地需求分析请求依次经过提取、澄清、分析与风险并行、汇总；后续在入口加入分类节点，才能让分析、查询和闲聊分别进入自己的路径。现有五个 Agent 仍可在图节点内部复用。

**8.1 至少会讲会用的答案：**“分析 Excel 导入需求”应进入需求分析路径；“查询 REQ-001 的状态”应进入查询路径；“你好”应进入闲聊路径。分类节点写入 `intent`，条件边读取该值选择目标节点。当前本地代码已经实现 8.3 的需求分析图；8.4 的三类分流仍在教学准备阶段。

### 8.1 检查题与参考答案

1. 系统新增“查询需求状态”和“普通闲聊”功能。现有五个 Agent 可以继续使用，入口需要增加什么判断？这个判断会怎样影响后续路径？

   **答案：**在入口增加意图分类节点，判断输入属于分析、查询还是闲聊，并写入 `intent`。条件边读取分类结果：分析进入已有五阶段图，查询进入真实数据查询节点，闲聊进入对话节点。这样每类请求都有适合的执行路径；例如“查询 REQ-001 的状态”应查询可信数据源并返回状态。

2. 报告缺少“开发排期”这一节。你希望系统检查后自动修改，最多修改两次。这里有哪些模型任务，以及哪些执行规则需要由程序定义？

   **答案：**模型承担检查报告和根据意见修订报告两个任务。程序定义评审后进入修订的条件、修订后返回评审的回边，以及最多修订两次的上限。State 保存报告、评审意见和修订次数；评审通过时结束，达到上限时结束并保留质量状态。达到上限表示停止修订，质量结果仍按最后一次评审记录。

## 8.2 LangGraph 核心概念

### 本块的学习目标

| 层次 | 学完 8.2 应达到的具体结果 |
| --- | --- |
| 必背 | State 保存本次图执行中各节点要共享的数据；Node 读取 State 并写入本步骤结果；Edge 指定下一步。能说出固定边、条件边、回边的用途。 |
| 至少会讲会用 | 给“企业管理员批量导入 Excel，最多一万行”和“做个导入功能”两种输入，能沿当前图说出每一步写入的字段、澄清后的分支以及分析和风险的汇合。 |
| 了解 | 知道 reducer 决定更新字段时如何合并；子图能封装带循环的步骤；Checkpointer、interrupt 和 updates 事件分别支持图级恢复、人工确认和进度展示。 |

**8.2 必背标准答案：**LangGraph 的 State 保存一次图执行中各步骤要共享的数据，例如原始输入、提取结果和分析报告。Node 是执行一步的函数，它读取需要的 State 字段，再写回本步骤的结果。Edge 规定执行顺序：固定边直接进入下一步，条件边读取 State 后选择路线，回边使流程返回前面的步骤继续执行。需求分析图中，提取节点写 `extractResult`，澄清节点写 `clarificationQuestions`，条件边根据问题列表决定结束或进入分析。

### 8.2.1 State：节点之间传递的工作记录

本地 `RequirementAnalysisState` 保存本次图执行中跨步骤使用的数据：`input` 是传入的需求，`retrievedContext` 是相关文档片段，`extractResult` 是提取结果，`clarificationQuestions` 保存需要向用户追问的问题，`analysisResult` 与 `riskResult` 保存并行步骤的产出，`report` 是最终报告。节点读取需要的字段，并返回本步骤写入的字段。

从工作流设计出发，跨节点要读取的数据放进 State。比如 `summaryStep` 要看分析结果，所以 `analysisResult` 保存在 State；只在某个节点内部使用的临时提示词字符串留在该函数中。节点调用模型时再组织提示词，便于调试每一步读到了什么。

`messages` 使用 `MessagesAnnotation.spec` 提供的消息合并规则；后续模型或工具消息可以加入已有消息。`report`、`analysisResult` 等草稿字段使用 `Annotation<T>()`，新结果会覆盖旧值。当前安装的 LangGraph 1.4.15 要求：填写 `default` 时，同时填写 `reducer`；本章这些字段由对应节点写入。下面展示本地已存在的核心字段：

```ts
const RequirementState = Annotation.Root({
  ...MessagesAnnotation.spec,
  input: Annotation<string>(),
  extractResult: Annotation<string>(),
  clarificationQuestions: Annotation<string[]>(),
  analysisResult: Annotation<string>(),
  riskResult: Annotation<string>(),
  report: Annotation<string>(),
});
```

理解 reducer 可以看后续 8.6 的具体变化：actor 写入 `report = '初稿'`，refine 写入 `report = '修订稿'`，覆盖规则使当前 State 中的 `report` 成为“修订稿”。8.5 中 agent 写入一条 AIMessage，tools 再写入一条 ToolMessage，消息通道保留两条供下一轮 agent 读取。报告采用覆盖规则，消息采用累积规则。

### 8.2.2 Node：完成一项明确任务

节点是接收 State、返回局部更新的函数。例如 `extractStep` 读 `input`，调用已有 `extractAgent`，返回 `{ extractResult: 结果 }`；`summaryStep` 读取 `extractResult`、`analysisResult`、`riskResult` 和 `retrievedContext`，返回 `{ report: 报告 }`。节点返回的字段由图合并到 State，其他字段继续保留。设计节点时先写清“读哪些字段、写哪些字段”。

```ts
async function extractStep(state: typeof RequirementState.State) {
  const extractResult = await extractAgent.invoke({ input: state.input });
  return { extractResult };
}
```

这段节点只承担“提取”一件事。它没有决定下一步去哪里；图上的边负责这个决定。节点异常时，图会在该步骤报错，调用方才能识别哪个阶段失败；后续可为特定节点配置重试或恢复策略。

### 8.2.3 Edge：决定下一步

固定边 `extractStep → clarifyStep` 表示提取后执行澄清。条件边读取当前 State，再选择目标：`clarificationQuestions` 有内容时进入 `END`，问题列表为空时进入分析与风险节点。`START` 和 `END` 是图的入口与出口。后续 8.4 的 classifier 同样通过条件边把 `intent` 为 `analyze`、`query`、`chat` 的输入送入各自路径。

本地基线的路径应画成：

```text
START → extractStep → clarifyStep ──有问题───────→ END
                                └─无问题─┬→ analysisStep ─┐
                                         └→ riskStep ─────┴→ summaryStep → END
```

这张图保留本地 `Promise.all([analysisAgent, riskAgent])` 的并行关系；课程正文里的单线 `analysis → risk` 是教学简图。到 8.3 移植时，以本地已有行为和可验证结果为准。

沿着一条输入追踪：`START` 把初始 State 送给 `extractStep`；它写 `extractResult`；固定边进入 `clarifyStep`；它写 `clarificationQuestions`；条件边据此结束或分出分析/风险两条路径；两条结果齐备后 `summaryStep` 写 `report`；`END` 返回最终 State。澄清分支由调用层根据 `clarificationQuestions` 映射为 `need_clarification` 响应。条件边选择目标节点，目标节点负责生成结果。

下面用两次请求观察 State。字段值仅用于教学示意，模型实际措辞会变化。

| 时刻 | 输入 A：描述完整 | 输入 B：描述模糊 |
| --- | --- | --- |
| 调用图时 | `input = "批量导入 Excel，最多一万行，失败行可导出"` | `input = "做个导入功能"` |
| extract 后 | `extractResult = "Excel / 一万行 / 失败导出"` | `extractResult = "导入功能，缺少格式和规则"` |
| clarify 后 | `clarificationQuestions = []` | `clarificationQuestions = ["支持什么格式？"]` |
| 条件边 | 同时进入 analysis、risk | 进入 END |
| 结束时 | `analysisResult`、`riskResult`、`report` 有值 | 返回澄清问题；本次未生成 `report` |

这里的关键是“先看 State 再走边”。分析节点只处理分析，风险节点只处理风险，条件边负责根据澄清结果选择路径。并行汇合时，两个节点写不同字段；summary 在两份结果都准备好后执行。

### 8.2.4 回边与子图

回边让流程再次进入前面的节点。8.5 的 `agent → tools → agent` 在工具结果到达后重新决定下一步；8.6 的 `critic → refine → critic` 在修订后重新评审。每条回边都要有业务退出条件和最大次数，确保任务能结束。子图把这些内部步骤包装成主图中的一个节点：主图只关心 `analysisResult` 或 `summary`，子图负责自己的循环。

ReAct 子图的一轮是：agent 决定调用 `search_requirement` → tools 返回需求详情 → agent 结合详情再次判断；信息够了就输出分析结论。Critic-Refine 子图的一轮是：critic 指出报告缺少排期依赖 → refine 修改该处 → critic 重新检查。两种循环的计数字段分别记录工具轮次和修订次数。主图把整个 analysis 子图当作一个节点，子图结束时将结果写回主图 State。

### 8.2.5 Checkpointer、人工中断和流式事件

Checkpointer 保存图运行过程中的 State 快照，用于图级恢复；本地 PostgreSQL `messages` 表保存的是用户会话历史，两者解决不同的持久化需求。`interrupt()` 可以暂停图，`Command({ resume })` 把用户确认结果送回图；这条图级暂停恢复链需要 Checkpointer。`streamMode: 'updates'` 按节点产生状态增量，可用于前端展示实际执行路径。这些能力在 8.7 结合本地服务边界决定是否接入。

一个具体场景是风险节点准备创建外部工单：图先用 `interrupt()` 交出“工单摘要和确认问题”，前端显示确认组件；用户确认后，以同一个 `thread_id` 和 `Command({ resume: true })` 继续图。另一个场景是前端进度条：`updates` 每完成一个节点发出该节点写入的字段，页面可将实际节点路径展示出来。8.7 会区分已在本地落地的业务消息存储、计划接入的节点进度，以及需要另行实现的图级人工中断。

### 8.2.6 最小示例：一句话走向不同节点

下面是独立教学示例，使用本地 LangGraph 1.4.15 可通过类型检查的 `Annotation` 写法。它演示 State、Node、固定边和条件边。

```ts
import { Annotation, StateGraph, START, END } from '@langchain/langgraph';

const State = Annotation.Root({
  input: Annotation<string>(),
  intent: Annotation<'analyze' | 'chat'>(),
  output: Annotation<string>(),
});

const classify = (state: typeof State.State) => ({
  intent: state.input.includes('需求') ? 'analyze' as const : 'chat' as const,
});

const analyze = (state: typeof State.State) => ({
  output: `收到需求：${state.input}`,
});

const chat = (state: typeof State.State) => ({
  output: `你好，你说的是：${state.input}`,
});

const graph = new StateGraph(State)
  .addNode('classify', classify)
  .addNode('analyze', analyze)
  .addNode('chat', chat)
  .addEdge(START, 'classify')
  .addConditionalEdges('classify', (state) => state.intent, {
    analyze: 'analyze',
    chat: 'chat',
  })
  .addEdge('analyze', END)
  .addEdge('chat', END)
  .compile();

const result = await graph.invoke({ input: '我想增加批量导入需求' });
console.log(result.intent, result.output);
// analyze 收到需求：我想增加批量导入需求
```

按执行顺序读这段代码：`invoke` 提交初始 State；`classify` 读 `input` 写 `intent`；条件边根据 `intent` 选择 `analyze`；`analyze` 写 `output`；固定边到 `END`；最终结果含原始输入、分类和输出。把输入改成“你好”，分类会写 `chat`，图会执行 `chat` 节点。这个例子没有模型调用，便于单独观察图如何运行；真实业务中的分类节点会在 8.4 加入模型和降级规则。

这里的关键词判断只用于观察图的分流动作。8.4 会把分类节点升级为适合业务的意图判断，并为查询接入可信数据源。课程原始算术示例使用 `eval`；本示例用需求分流展示相同的图原语。

### 8.2.7 本地文件与版本

8.3 的目标文件是 `services/chat/src/llm/graph/requirement-analysis-graph.ts`，随后调整现有 `agents/orchestrator.service.ts` 的调用入口。课程参考版本为 `@langchain/langgraph@^1.2.9`；本地安装版本为 1.4.15，代码以本地类型检查结果为准。

当前文件分工：`sub-agents.ts` 定义五条 LangChain Agent；`requirement-analysis-graph.ts` 定义 State、节点和边；`orchestrator.service.ts` 保留 NestJS 编排入口，并把图结果映射为现有返回结构。图文件解决流程控制问题，现有 Agent 文件解决每一步的模型调用问题。课程使用 `Annotation.Root`；本地安装版本为 1.4.15，现有实现已通过类型检查和构建，真实接口行为仍需用户验收。

### 本块检查

给出“分析一个需求”输入后，能口述：`input` 存在 State 中；`extractStep` 写入 `extractResult`；`clarifyStep` 写入 `clarificationQuestions`，条件边据此决定是否提前结束；信息充分时 `analysisStep` 与 `riskStep` 并行写入各自结果；`summaryStep` 汇合两个结果写入 `report`。后续报告修订应覆盖旧值；工具消息应在消息通道中累积。做到这一点即可进入 8.3。

### 8.2 检查题与参考答案

1. 澄清节点返回了两个追问问题。问题应该保存在哪个 State 字段？谁根据它决定结束？接口随后应该返回什么？

   **答案：**澄清节点把问题写入 `clarificationQuestions`。澄清后的条件边读取这个数组，有问题时进入 `END`；调用层把图结果整理为 `status: need_clarification` 和 `clarificationQuestions`，供用户补充信息。提取节点的 `isComplete` 是模型提取结果中的一个字段，当前路径由澄清问题数组决定。

2. 分析与风险同时执行，汇总需要读取它们的结果。应该怎样设计字段和边？

   **答案：**分析节点写 `analysisResult`，风险节点写 `riskResult`，两个节点分别写自己的字段。澄清后的条件边同时进入两个节点；两节点共同汇入汇总节点，汇总等两份结果齐备后执行，再写入 `report`。这个设计让两种结果能够分别保存，并确保汇总读取到本轮完整结果。

## 8.3 基线迁移：把现有五阶段流程放进图

本块只改变编排方式。用户输入仍先提取、再澄清；信息不足时返回问题；信息充分时分析与风险并行；最后汇总报告。`OrchestratorService` 保留原有响应结构，外部接口继续通过 `POST /api/conversations/:id/chat` 使用。

### 本块的学习目标

| 层次 | 学完 8.3 应达到的具体结果 |
| --- | --- |
| 必背 | 能说出 State 保存本次执行的数据、Node 执行一步、Edge 指定下一步；能按顺序复述“提取 → 澄清 → 分析与风险并行 → 汇总”，并说明有澄清问题时提前结束。 |
| 至少会讲会用 | 给出一条需求，能指出 `extractStep`、`clarifyStep`、`analysisStep`、`riskStep`、`summaryStep` 各读写哪个字段；能说明 `requirement-analysis-graph.ts` 定义流程，`orchestrator.service.ts` 调用图并整理接口结果；能通过 Apifox 检查 `status`、`usedAgents`、`steps`、`report`。 |
| 了解 | 知道 `MessagesAnnotation.spec` 为后续消息累积留出字段，当前 8.3 尚未写入图消息；知道图每次请求独立执行，会话历史仍由数据库保存；8.4 再加入分析／查询／闲聊的路由。 |

**8.3 必背标准答案：**当前需求分析图按“提取 → 澄清 → 分析与风险并行 → 汇总”执行。`extractStep` 写提取结果，`clarifyStep` 写澄清问题；有问题时条件边直接结束，信息充分时分析与风险分别写结果，汇总节点等两份结果齐备后生成报告。`requirement-analysis-graph.ts` 管步骤和路线，`orchestrator.service.ts` 调用图并把结果整理成聊天接口使用的字段。

学完后自己检查两个情形：一条信息完整的需求会走过哪些节点并产出哪些字段？一条需要追问的需求在哪一步结束，返回给接口哪些字段？能够用自己的话回答，并在 Apifox 的真实响应中找到对应字段，就达到本块目标。

### 先沿一条真实请求看两个文件的作用

例子：用户在已有会话中发送“企业管理员需要批量导入 Excel，最多一万行，错误行可导出”。`ConversationController` 先验证会话属于当前用户；`AdvancedAnalysisService` 读取数据库里的历史消息，检索当前用户文档，把历史与本轮输入组成 `enrichedInput`，把检索片段组成 `retrievedContext`。随后它调用 `OrchestratorService.orchestrate(enrichedInput, retrievedContext)`。这里以前直接顺序调用五个 Agent；现在由 `OrchestratorService` 调用 `runAnalysisGraph()`。图运行结束后，`OrchestratorService` 把图数据整理为原接口的 `status`、`usedAgents`、`steps`、`report` 等字段；`AdvancedAnalysisService` 再保存消息，并附上 `retrievedDocuments` 返回给客户端。

图运行时有一份共享数据（State）。启动时至少含 `input`（本轮分析输入）、`retrievedContext`（检索片段）和空的 `messages`。`extractStep` 读 `input`，写 `extractResult`；`clarifyStep` 读 `input` 和 `extractResult`，写 `clarificationQuestions`。若问题列表非空，图到此结束，服务返回 `need_clarification`。若问题列表为空，`analysisStep` 和 `riskStep` 同时读取 `extractResult`，分别写 `analysisResult` 和 `riskResult`；`summaryStep` 等两份结果齐备后，结合 `retrievedContext` 写入 `report`。`extractResult` 等字段只是数据名；Agent 真正如何提取、评估和写报告，仍由 `sub-agents.ts` 的提示词链完成。

因此可以直接从业务问题理解四个术语：State 是运行一次图时各步骤共享的数据；Node 是执行一个步骤的函数；Edge 指定步骤完成后进入哪里；条件边根据 `clarificationQuestions` 决定提前结束或继续分析。`Annotation<string>()` 声明该字段存字符串；这些业务字段后续写入时覆盖旧值。`MessagesAnnotation.spec` 提供可累积的消息字段，但当前 8.3 传入空 `messages`，五个业务节点尚未往里面写消息。当前会话历史仍由数据库的 `messages` 表保存；这张图每次请求独立运行，尚未使用 LangGraph Checkpointer。

另一条输入“做个导入功能”可能被澄清 Agent 判为信息不足：图只执行提取与澄清，返回要追问的问题。这个分支说明了条件边的作用，也解释了为什么 `report` 在澄清响应中可以为空。模型判断有波动，验收时看实际 `status` 和经过的步骤。

### 为什么需要两个文件

1. 新建 `services/chat/src/llm/graph/requirement-analysis-graph.ts`：定义共享数据、五个执行步骤和步骤之间的路线。
2. 修改 `services/chat/src/llm/agents/orchestrator.service.ts`：保留 NestJS 对外入口，把图的最终结果整理成当前接口使用的响应。

`sub-agents.ts` 保持原样；五个节点内部直接调用已经存在的五条 LangChain Agent。本地 chat 使用 ESM，新增相对 import 带 `.js`。

### 安装依赖

在 PowerShell 中执行：

```powershell
cd "C:\Users\Administrator\Desktop\newAgent\agent-course\chapter-02-工程底座\llm"
bun add @langchain/langgraph@1.4.15 --cwd services/chat
```

课程分支写 `^1.2.9`；本地锁文件已有满足该版本范围的 `1.4.15` 包。本章给出的并行分支与汇合写法已用本地 `1.4.15` 做无模型图运行验证。

### 完整文件 1：`services/chat/src/llm/graph/requirement-analysis-graph.ts`

```ts
import {
  Annotation,
  END,
  MessagesAnnotation,
  START,
  StateGraph,
} from '@langchain/langgraph';
import {
  analysisAgent,
  clarifyAgent,
  extractAgent,
  riskAgent,
  summaryAgent,
} from '../agents/sub-agents.js';

export const RequirementAnalysisState = Annotation.Root({
  ...MessagesAnnotation.spec,
  input: Annotation<string>(),
  retrievedContext: Annotation<string>(),
  extractResult: Annotation<string>(),
  clarifyRaw: Annotation<string>(),
  clarificationQuestions: Annotation<string[]>(),
  analysisResult: Annotation<string>(),
  riskResult: Annotation<string>(),
  report: Annotation<string>(),
});

function parseJsonLoose(raw: string): unknown {
  const cleaned = raw
    .trim()
    .replace(/^```(?:json)?/i, '')
    .replace(/```$/i, '')
    .trim();
  return JSON.parse(cleaned);
}

async function extractStep(
  state: typeof RequirementAnalysisState.State,
) {
  const extractResult = await extractAgent.invoke({
    input: state.input,
  });
  return { extractResult };
}

async function clarifyStep(
  state: typeof RequirementAnalysisState.State,
) {
  const clarifyRaw = await clarifyAgent.invoke({
    input: state.input,
    extractResult: state.extractResult,
  });

  let clarificationQuestions: string[] = [];
  try {
    const result = parseJsonLoose(clarifyRaw) as {
      needsClarification?: boolean;
      questions?: string[];
    };
    if (
      result?.needsClarification
      && Array.isArray(result.questions)
    ) {
      clarificationQuestions = result.questions;
    }
  } catch {
    // 与原编排一致：解析失败时继续分析。
  }

  return { clarifyRaw, clarificationQuestions };
}

async function analysisStep(
  state: typeof RequirementAnalysisState.State,
) {
  const analysisResult = await analysisAgent.invoke({
    input: state.input,
    extractResult: state.extractResult,
  });
  return { analysisResult };
}

async function riskStep(
  state: typeof RequirementAnalysisState.State,
) {
  const riskResult = await riskAgent.invoke({
    input: state.input,
    extractResult: state.extractResult,
  });
  return { riskResult };
}

async function summaryStep(
  state: typeof RequirementAnalysisState.State,
) {
  const report = await summaryAgent.invoke({
    input: state.input,
    extractResult: state.extractResult,
    analysisResult: state.analysisResult,
    riskResult: state.riskResult,
    retrievedContext: state.retrievedContext,
  });
  return { report };
}

export function createAnalysisGraph() {
  return new StateGraph(RequirementAnalysisState)
    .addNode('extractStep', extractStep)
    .addNode('clarifyStep', clarifyStep)
    .addNode('analysisStep', analysisStep)
    .addNode('riskStep', riskStep)
    .addNode('summaryStep', summaryStep)
    .addEdge(START, 'extractStep')
    .addEdge('extractStep', 'clarifyStep')
    .addConditionalEdges(
      'clarifyStep',
      (state): typeof END | ['analysisStep', 'riskStep'] =>
        state.clarificationQuestions.length > 0
          ? END
          : ['analysisStep', 'riskStep'],
    )
    .addEdge(
      ['analysisStep', 'riskStep'],
      'summaryStep',
    )
    .addEdge('summaryStep', END)
    .compile();
}

export async function runAnalysisGraph(
  input: string,
  retrievedContext = '无相关参考文档',
) {
  return createAnalysisGraph().invoke({
    input,
    retrievedContext,
    messages: [],
  });
}
```

### 完整文件 2：`services/chat/src/llm/agents/orchestrator.service.ts`

```ts
import { Injectable } from '@nestjs/common';
import {
  runAnalysisGraph,
} from '../graph/requirement-analysis-graph.js';

@Injectable()
export class OrchestratorService {
  async orchestrate(
    input: string,
    retrievedContext = '无相关参考文档',
  ) {
    try {
      const result = await runAnalysisGraph(
        input,
        retrievedContext,
      );

      if (result.clarificationQuestions.length > 0) {
        return {
          mode: 'fixed_workflow',
          status: 'need_clarification' as const,
          clarificationQuestions:
            result.clarificationQuestions,
          usedAgents: ['extractAgent', 'clarifyAgent'],
          fallback: 'ask_user',
        };
      }

      return {
        mode: 'fixed_workflow',
        status: 'completed' as const,
        clarificationQuestions: [],
        usedAgents: [
          'extractAgent',
          'clarifyAgent',
          'analysisAgent',
          'riskAgent',
          'summaryAgent',
        ],
        fallback: null,
        steps: {
          extract: result.extractResult,
          analysis: result.analysisResult,
          risk: result.riskResult,
        },
        report: result.report,
      };
    } catch (error) {
      return {
        mode: 'fixed_workflow',
        status: 'failed' as const,
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

### 逐段理解与验收

五个函数就是五个原有业务步骤；函数内部的 `invoke()` 参数与原编排一致。State 保存上一步产出的结果，下一步从 State 读取。澄清后看 `clarificationQuestions.length`：有问题则结束；没有问题则并行运行 analysis/risk；`addEdge(['analysisStep', 'riskStep'], 'summaryStep')` 让汇总等两份结果齐备。`OrchestratorService` 保留旧的响应字段，前端和已有接口继续读取同一结构。

复制后，在 `services/chat` 目录执行 `bun run typecheck` 和 `bun run build`。用户自行启动 chat。**本地 3002 首页仍是第六章的 AI 需求分析助手，页面调用 `/api/ui-chat/chat` 与 `/api/ui-chat/action`；它尚未接到本章的 LangGraph 分析入口。8.3 的真实链路使用 Apifox 验证。**数据清空后从以下三个请求重新开始：

1. `POST http://localhost:4002/api/auth/login`，Body JSON：`{"username":"admin","password":"Admin@123456"}`。user-system 响应中的 `data.accessToken` 是后续两个请求的 Bearer Token。
2. `POST http://localhost:4001/api/conversations`，Authorization 选择 Bearer Token，Body JSON：`{"title":"第八章 LangGraph 验证"}`。chat 响应顶层的 `id` 是新生成的会话 ID；复制这个值，例如返回 `{"id":"cm...","title":"..."}` 时复制 `cm...`。
3. `POST http://localhost:4001/api/conversations/刚复制的id/chat`，Authorization 使用同一个 Bearer Token，Body JSON 如下。URL 中的 `刚复制的id` 要替换为第二步响应中的完整 `id`，不保留中文占位字。

```json
{
  "input": "分析一个批量导入 Excel 的功能：最多一万行，失败行可导出，目标用户是企业管理员"
}
```

预期 `status = completed`，`usedAgents` 包含五个名称，`steps.extract/analysis/risk` 与 `report` 有内容。再输入 `{"input":"做个导入功能"}`，若澄清 Agent 判定条件不足，预期 `status = need_clarification`，`usedAgents` 只有提取和澄清。模型判断存在波动，验收时重点观察路由与字段；`GET /api/conversations/<ID>/messages` 可检查成功轮次的会话记录。

当前进度：文件 1 `requirement-analysis-graph.ts` 和文件 2 `orchestrator.service.ts` 均已复制接入。LangGraph 1.4.15 的 `Annotation` 类型问题已修正；两个文件一起执行 `bun run typecheck` 与 `bun run build` 均通过。学习者已在 Apifox 使用真实 Token、新建会话和 Excel 批量导入需求完成接口验收：`status = completed`，五个 Agent 名称、提取/分析/风险三份步骤结果及最终 `report` 均返回。8.3 的成功路径已验收；澄清提前结束分支仍可用另一条模糊输入单独检查。8.4 路由教学代码已准备，业务文件仍保留 8.3 版本。

本次真实响应的两个教学观察：`steps.extract` 内的 `isComplete = false`、`missingFields = [businessGoal, priority]` 反映提取 Agent 认为需求内容尚不完整；接口 `status = completed` 表示图本轮走到了报告节点。现有澄清 Prompt 只在核心功能或目标用户缺失时追问，业务目标和优先级缺失会留给分析环节，所以这次 `clarificationQuestions = []` 与现有设计一致。图的实际分支读取该问题列表，随后继续执行分析与风险。`retrievedDocuments` 返回了 BLE/烫珠板片段，说明检索按相似度返回了当前用户文档中的片段；报告明确指出它们与 Excel 导入无关。检索相关性与引用阈值属于后续 RAG 质量改进，当前 8.3 验收聚焦五阶段图的控制流与接口结果。

### 8.3 必背与检查题

**必背标准答案：**`requirement-analysis-graph.ts` 定义共享数据、执行节点和边；`runAnalysisGraph` 提交初始数据并运行图。`OrchestratorService` 调用它，并将图结果整理成接口使用的状态、步骤结果和报告。五个节点内部继续复用原有 LangChain Agent。澄清问题非空时结束，问题为空时并行执行分析与风险，等两份结果完成后汇总。

1. `requirement-analysis-graph.ts` 和 `orchestrator.service.ts` 分别负责什么？一次聊天请求怎样经过这两个文件？

   **答案：**图文件负责流程定义和执行，服务文件负责 NestJS 编排入口及响应整理。聊天业务服务调用 `orchestrate`，它调用 `runAnalysisGraph`；图执行节点并返回最终 State，`orchestrate` 再将结果整理成 `status`、`steps` 和 `report`，供业务服务持久化并返回。

2. 需求存在追问问题时，为什么本次只出现两个 `usedAgents`？能够继续时，汇总怎样保证拿到分析和风险两份结果？

   **答案：**提取和澄清执行后，条件边发现 `clarificationQuestions` 非空，进入 `END`，调用层返回两个 Agent 名称及追问问题。问题为空时，条件边进入分析和风险两个节点；`addEdge(['analysisStep', 'riskStep'], 'summaryStep')` 要求两节点完成后再运行汇总，因此汇总能读取本轮两份结果。

## 8.4 加路由层：分析、查询、闲聊走各自的路径

### 本块的学习目标

| 层次 | 具体达标要求 |
| --- | --- |
| 必背 | Router 节点读取当前用户输入，把意图写入 `intent`；条件边读取 `intent`，选择分析、查询或闲聊路径。查询和闲聊到各自处理节点后结束；分析进入 8.3 的原有五阶段图。 |
| 至少会讲会用 | 给“分析 Excel 导入”“查询 REQ 编号状态”“你好”三种输入，能说出各自路径、返回字段和用于验证的接口；能解释为什么分类依据是本轮输入，历史对话仍供分析参考。 |
| 了解 | 知道模型分类可以使用 Zod 结构化输出约束格式，并用明确规则兜底；本地尚无按 REQ 编号查询的需求状态表，查询分支只能如实说明目前无法核实状态。 |

**8.4 必背标准答案：**Router 是图的入口节点，负责判断本轮用户输入属于分析、查询还是闲聊，并把结果写入 State 的 `intent`。条件边读取 `intent`：`analyze` 进入原有提取到汇总的分析路径，`query` 进入查询处理节点，`chat` 进入闲聊处理节点。查询和闲聊结束后直接到 `END`，所以它们跳过五阶段分析。

### 本地实现前先看完整调用链

第八章 8.3 的真实请求已经跑通五阶段分析。8.4 在它前面加入 `classifier`。用户发送“查询 REQ-20240315-001 的状态”时，`ConversationController` 仍先校验会话归属，`AdvancedAnalysisService` 仍提供数据库历史；它将 `enrichedInput` 用于分析上下文，同时把 `input` 原话单独传给图的 `currentInput`。`classifier` 只看 `currentInput`，写入 `intent = query`；条件边进入 `queryHandler`。本地没有需求编号状态表，因此 `queryHandler` 返回“当前无法核实状态”的真实说明。`OrchestratorService` 把图结果整理为 `intent`、`status`、`queryResponse`、`report`，业务层按原有流程持久化消息。

输入“分析 Excel 导入需求”时，`intent = analyze`，进入提取、澄清、分析与风险、汇总；输入“你好，今天天气不错”时，`intent = chat`，只执行闲聊节点。`retrievedDocuments` 只在分析响应中返回；当前 `AdvancedAnalysisService` 仍在路由前尝试文档检索，因此查询和闲聊路径仍可能承担一次检索开销，这是后续优化点。当前 3002 页面使用第六章独立的 UI 状态机；8.4 继续由 Apifox 验证真实图入口。

本块涉及四处文件：新建 `prompts/graph-router.prompt.ts` 存放分类与闲聊提示词；修改 `graph/requirement-analysis-graph.ts` 增加 State 字段、分类节点、查询/闲聊节点和条件边；修改 `agents/orchestrator.service.ts` 将不同图结果整理为原接口字段；修改 `advanced-analysis.service.ts` 把本轮原始输入作为 `currentInput` 传给图，并只在分析响应里列出检索片段。下方代码按本地 NestJS 12、ESM 与 LangGraph 1.4.15 准备。

### 本块代码与验收

学习者按下方文件顺序复制；目前 8.4 代码仍处于教学准备状态，本地业务文件保留 8.3 版本。代码在临时预览文件中已通过 `bun run typecheck`；查询分支通过无模型运行验证。复制后仍需学习者自己重启 4001、用真实模型和 Apifox 验证三条路径。

### 文件 1：prompts/graph-router.prompt.ts

```ts
export const ROUTER_SYSTEM_PROMPT = `你负责把用户本轮输入分成三类，并只输出 JSON 对象。
analyze：用户提出新需求、要求分析方案、风险或复杂度。
query：用户询问已有需求编号的详情、状态、进度或报告。
chat：问候、感谢或普通闲聊。
有需求编号且询问状态、进度、详情或报告时优先 query；纯问候优先 chat；其余默认 analyze。
返回格式：{"intent":"analyze|query|chat","reasoning":"一句话理由"}。`;

export const CHAT_SYSTEM_PROMPT =
  '你是友好的需求分析助手。对普通问候简短回复，并引导用户描述需求。';
```

### 文件 2：graph/requirement-analysis-graph.ts

```ts
import {
  Annotation,
  END,
  MessagesAnnotation,
  START,
  StateGraph,
} from '@langchain/langgraph';
import { z } from 'zod';
import {
  analysisAgent,
  clarifyAgent,
  extractAgent,
  riskAgent,
  summaryAgent,
} from '../agents/sub-agents.js';
import { createChatModel } from '../model.factory.js';
import {
  CHAT_SYSTEM_PROMPT,
  ROUTER_SYSTEM_PROMPT,
} from '../prompts/graph-router.prompt.js';

type Intent = 'analyze' | 'query' | 'chat';

const intentSchema = z.object({
  intent: z.enum(['analyze', 'query', 'chat']),
  reasoning: z.string(),
});

export const RequirementAnalysisState = Annotation.Root({
  ...MessagesAnnotation.spec,
  input: Annotation<string>(),
  currentInput: Annotation<string>(),
  retrievedContext: Annotation<string>(),
  intent: Annotation<Intent>(),
  queryResponse: Annotation<string>(),
  chatResponse: Annotation<string>(),
  extractResult: Annotation<string>(),
  clarifyRaw: Annotation<string>(),
  clarificationQuestions: Annotation<string[]>(),
  analysisResult: Annotation<string>(),
  riskResult: Annotation<string>(),
  report: Annotation<string>(),
});

function fallbackIntent(input: string): Intent {
  const hasRequirementId = /\bREQ-[A-Za-z0-9-]+\b/i.test(input);
  const asksToRead = /查询|查看|看看|状态|进度|详情|报告|怎么样|如何/.test(input);
  if (hasRequirementId && asksToRead) return 'query';
  if (/^(你好|您好|嗨|早上好|晚上好|谢谢|感谢)/.test(input.trim())
    && !/需求|功能|查询|分析/.test(input)) {
    return 'chat';
  }
  return 'analyze';
}

async function classifierStep(state: typeof RequirementAnalysisState.State) {
  const input = state.currentInput.trim();
  const ruleIntent = fallbackIntent(input);
  if (ruleIntent === 'query' || ruleIntent === 'chat') {
    return { intent: ruleIntent };
  }
  try {
    const model = createChatModel().withStructuredOutput(
      intentSchema,
      { method: 'jsonMode' },
    );
    const result = await model.invoke([
      { role: 'system', content: ROUTER_SYSTEM_PROMPT },
      { role: 'user', content: input },
    ]);
    return { intent: result.intent };
  } catch {
    return { intent: fallbackIntent(input) };
  }
}

function queryHandler(state: typeof RequirementAnalysisState.State) {
  const requirementId = state.currentInput.match(/\bREQ-[A-Za-z0-9-]+\b/i)?.[0];
  const queryResponse = requirementId
    ? `当前系统尚未接入 ${requirementId} 的状态数据，暂时无法核实这条需求的进度。`
    : '当前系统尚未接入按编号查询需求状态的数据。';
  return { queryResponse, report: queryResponse };
}

async function chatHandler(state: typeof RequirementAnalysisState.State) {
  const response = await createChatModel().invoke([
    { role: 'system', content: CHAT_SYSTEM_PROMPT },
    { role: 'user', content: state.currentInput },
  ]);
  const chatResponse = response.text;
  return { chatResponse, report: chatResponse };
}

function parseJsonLoose(raw: string): unknown {
  const cleaned = raw.trim()
    .replace(/^```(?:json)?/i, '')
    .replace(/```$/i, '')
    .trim();
  return JSON.parse(cleaned);
}

async function extractStep(state: typeof RequirementAnalysisState.State) {
  const extractResult = await extractAgent.invoke({ input: state.input });
  return { extractResult };
}

async function clarifyStep(state: typeof RequirementAnalysisState.State) {
  const clarifyRaw = await clarifyAgent.invoke({
    input: state.input,
    extractResult: state.extractResult,
  });
  let clarificationQuestions: string[] = [];
  try {
    const result = parseJsonLoose(clarifyRaw) as {
      needsClarification?: boolean;
      questions?: string[];
    };
    if (result?.needsClarification && Array.isArray(result.questions)) {
      clarificationQuestions = result.questions;
    }
  } catch {
    // 澄清结果解析失败时沿用原流程的继续分析策略。
  }
  return { clarifyRaw, clarificationQuestions };
}

async function analysisStep(state: typeof RequirementAnalysisState.State) {
  const analysisResult = await analysisAgent.invoke({
    input: state.input,
    extractResult: state.extractResult,
  });
  return { analysisResult };
}

async function riskStep(state: typeof RequirementAnalysisState.State) {
  const riskResult = await riskAgent.invoke({
    input: state.input,
    extractResult: state.extractResult,
  });
  return { riskResult };
}

async function summaryStep(state: typeof RequirementAnalysisState.State) {
  const report = await summaryAgent.invoke({
    input: state.input,
    extractResult: state.extractResult,
    analysisResult: state.analysisResult,
    riskResult: state.riskResult,
    retrievedContext: state.retrievedContext,
  });
  return { report };
}

function routeByIntent(state: typeof RequirementAnalysisState.State) {
  if (state.intent === 'query') return 'queryHandler';
  if (state.intent === 'chat') return 'chatHandler';
  return 'extractStep';
}

export function createAnalysisGraph() {
  return new StateGraph(RequirementAnalysisState)
    .addNode('classifier', classifierStep)
    .addNode('queryHandler', queryHandler)
    .addNode('chatHandler', chatHandler)
    .addNode('extractStep', extractStep)
    .addNode('clarifyStep', clarifyStep)
    .addNode('analysisStep', analysisStep)
    .addNode('riskStep', riskStep)
    .addNode('summaryStep', summaryStep)
    .addEdge(START, 'classifier')
    .addConditionalEdges('classifier', routeByIntent)
    .addEdge('queryHandler', END)
    .addEdge('chatHandler', END)
    .addEdge('extractStep', 'clarifyStep')
    .addConditionalEdges(
      'clarifyStep',
      (state): typeof END | ['analysisStep', 'riskStep'] =>
        state.clarificationQuestions.length > 0
          ? END
          : ['analysisStep', 'riskStep'],
    )
    .addEdge(['analysisStep', 'riskStep'], 'summaryStep')
    .addEdge('summaryStep', END)
    .compile();
}

export async function runAnalysisGraph(
  input: string,
  retrievedContext = '无相关参考文档',
  currentInput = input,
) {
  return createAnalysisGraph().invoke({
    input,
    currentInput,
    retrievedContext,
    messages: [],
  });
}
```

### 文件 3：agents/orchestrator.service.ts

```ts
import { Injectable } from '@nestjs/common';
import {
  runAnalysisGraph,
} from '../graph/requirement-analysis-graph.js';

@Injectable()
export class OrchestratorService {
  async orchestrate(
    input: string,
    retrievedContext = '无相关参考文档',
    currentInput = input,
  ) {
    try {
      const result = await runAnalysisGraph(
        input,
        retrievedContext,
        currentInput,
      );

      if (result.intent === 'query') {
        return {
          mode: 'routed_graph',
          intent: 'query' as const,
          status: 'completed' as const,
          clarificationQuestions: [],
          usedAgents: ['classifier', 'queryHandler'],
          fallback: null,
          queryResponse: result.queryResponse,
          report: result.report,
        };
      }

      if (result.intent === 'chat') {
        return {
          mode: 'routed_graph',
          intent: 'chat' as const,
          status: 'completed' as const,
          clarificationQuestions: [],
          usedAgents: ['classifier', 'chatHandler'],
          fallback: null,
          chatResponse: result.chatResponse,
          report: result.report,
        };
      }

      if (result.clarificationQuestions.length > 0) {
        return {
          mode: 'routed_graph',
          intent: 'analyze' as const,
          status: 'need_clarification' as const,
          clarificationQuestions: result.clarificationQuestions,
          usedAgents: ['classifier', 'extractAgent', 'clarifyAgent'],
          fallback: 'ask_user',
        };
      }

      return {
        mode: 'routed_graph',
        intent: 'analyze' as const,
        status: 'completed' as const,
        clarificationQuestions: [],
        usedAgents: [
          'classifier',
          'extractAgent',
          'clarifyAgent',
          'analysisAgent',
          'riskAgent',
          'summaryAgent',
        ],
        fallback: null,
        steps: {
          extract: result.extractResult,
          analysis: result.analysisResult,
          risk: result.riskResult,
        },
        report: result.report,
      };
    } catch (error) {
      return {
        mode: 'routed_graph',
        status: 'failed' as const,
        clarificationQuestions: [],
        usedAgents: ['classifier'],
        fallback: 'manual_review',
        report: '处理失败，请稍后重试。',
        error: String(error),
      };
    }
  }
}
```

### 文件 4：advanced-analysis.service.ts

```ts
import { Injectable } from '@nestjs/common';
import {
  MessageRole,
} from '../generated/prisma/client.js';
import {
  SearchService,
} from '../document/search.service.js';
import {
  DbChatHistory,
} from '../message/db-chat-history.js';
import {
  MessageService,
} from '../message/message.service.js';
import {
  OrchestratorService,
} from './agents/orchestrator.service.js';

@Injectable()
export class AdvancedAnalysisService {
  constructor(
    private readonly messageService:
      MessageService,
    private readonly searchService:
      SearchService,
    private readonly orchestrator:
      OrchestratorService,
  ) {}

  async analyze(
    userId: string,
    conversationId: string,
    input: string,
  ) {
    const history =
      new DbChatHistory(
        conversationId,
        this.messageService,
      );

    const messages =
      await history.getMessages();

    let retrievedDocuments:
      Awaited<
        ReturnType<
          SearchService['similaritySearch']
        >
      > = [];

    try {
      retrievedDocuments =
        await this.searchService
          .similaritySearch(
            input,
            userId,
            3,
          );
    } catch (error) {
      console.error(
        '[AdvancedAnalysis] 检索失败：',
        error,
      );
    }

    const retrievedContext =
      retrievedDocuments.length > 0
        ? retrievedDocuments
            .map(
              (document, index) =>
                [
                  `[文档片段 ${index + 1}]`,
                  `相关度：${
                    document.score.toFixed(3)
                  }`,
                  document.content,
                ].join('\n'),
            )
            .join('\n\n')
        : '无相关参考文档';

    const historyText =
      messages.length > 0
        ? messages
            .map((message) => {
              const content =
                typeof message.content
                  === 'string'
                  ? message.content
                  : JSON.stringify(
                      message.content,
                    );

              return [
                message.getType(),
                content,
              ].join(': ');
            })
            .join('\n')
        : '';

    const enrichedInput = [
      historyText
        ? `历史对话：\n${historyText}`
        : '',
      `当前输入：${input}`,
    ]
      .filter(Boolean)
      .join('\n\n');

    const result =
      await this.orchestrator
        .orchestrate(
          enrichedInput,
          retrievedContext,
          input,
        );

    const usedDocuments =
      result.intent === 'analyze'
        ? retrievedDocuments
        : [];

    await this.messageService.addMessage(
      conversationId,
      MessageRole.USER,
      input,
    );

    if (
      result.status
      !== 'need_clarification'
    ) {
      await this.messageService.addMessage(
        conversationId,
        MessageRole.ASSISTANT,
        result.report
          ?? '分析未完成',
        {
          usedAgents:
            result.usedAgents,
          retrievedDocuments:
            usedDocuments.length,
        },
      );
    }

    return {
      ...result,
      retrievedDocuments:
        usedDocuments.map(
          (document) => ({
            documentId:
              document.documentId,
            chunkId:
              document.chunkId,
            chunkIndex:
              document.chunkIndex,
            content:
              document.content.slice(
                0,
                200,
              ),
            score:
              document.score,
          }),
        ),
    };
  }
}
```

### 8.4 复制后的验证顺序

在 `C:\Users\Administrator\Desktop\newAgent\agent-course\chapter-02-工程底座\llm\services\chat` 执行 `bun run typecheck` 和 `bun run build`；学习者自己在 `llm` 目录运行 `bun run dev:chat`。Apifox 继续使用 8.3 中真实登录得到的 Bearer Token 与新建会话的 `id`，向 `POST http://localhost:4001/api/conversations/会话id/chat` 发送三条不同输入：

1. `{"input":"分析需求：企业管理员要批量导入 Excel，最多一万行"}` → `intent: analyze`；信息足够时有 `steps` 与 `report`，澄清时有 `clarificationQuestions`。
2. `{"input":"查询 REQ-20240315-001 的状态"}` → `intent: query`、`queryResponse` 有内容；`usedAgents` 包含 `classifier` 与 `queryHandler`，没有五阶段分析结果。由于本地没有需求编号状态表，回复应明确说明无法核实状态。
3. `{"input":"你好，今天天气不错"}` → `intent: chat`、`chatResponse` 有内容；`usedAgents` 包含 `classifier` 与 `chatHandler`，没有分析步骤结果。

三条请求可在同一个会话中测试；分类节点读取单独传入的 `currentInput`，所以先前消息出现在 `enrichedInput` 里时，不应改变本轮意图。聊天与查询仍会先进入业务层的文档检索逻辑，当前验收重点是图上的节点路径。每条请求返回后，可用 `GET /api/conversations/会话id/messages` 核对消息仍由数据库保存。

### 本块检查题与参考答案

1. **同一会话上轮分析 Excel，本轮问“查询 REQ-20240315-001 的状态”，分类应读取什么？**读取本轮原始 `currentInput`；它包含查询编号和状态的意图。历史对话继续供分析路径使用。
2. **为什么查询分支不给具体“进行中/已完成”状态？**本地数据库尚无按 REQ 编号保存与查询需求状态的数据表。查询节点返回可核实的数据边界，随后可接入真实需求系统。
3. **如何证明问候跳过了五阶段分析？**检查响应 `intent: chat`、`usedAgents` 只有分类和闲聊节点，`steps.extract/analysis/risk` 不出现；后端节点事件可在后续 8.7 进一步验证实际运行路径。
