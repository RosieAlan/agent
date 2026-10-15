# 第八章场景面试题

## 8.1 LangChain 与 LangGraph 的职责

### 问题 1：已有 extract、clarify、analysis、risk、summary 五个 Agent，为什么要引入 LangGraph？

参考答案：当前 `OrchestratorService` 已能完成固定分析路径，并在澄清后并行运行 analysis/risk。新需求包含分析、查询、闲聊分流，分析阶段可能多次调用工具，报告还需要评审修订。LangGraph 用共享 State、节点、条件边和回边明确表达这些运行时路径；节点内继续调用已有 LangChain Agent。

### 问题 2：用户说“查询 REQ-001 当前状态”，新增图应如何处理？

参考答案：classifier 将 `intent` 写为 `query`，条件边把请求送到查询节点。查询节点从可信业务数据源读取状态并形成响应，然后结束。查询结果需要事实依据，模型负责组织表达。

### 问题 3：数据库已经保存会话消息，图还需要 Checkpointer 吗？

参考答案：业务数据库保存用户会话与消息。Checkpointer 保存图运行中的节点状态，适用于图级断点恢复和 `interrupt()` 暂停后恢复。本章先保留已有业务持久化，8.7 再根据是否实现图级中断与恢复决定 Checkpointer。

## 8.2 State、Node 与 Edge

### 问题 1：分析与风险评估并行执行，图的 State 和边怎样设计？

参考答案：State 分别设 `analysisResult` 和 `riskResult` 两个字段。澄清通过后从该节点发出两条路径，分别执行分析和风险节点；两条路径完成后汇入 summary。两个节点各写自己的字段，summary 读取两份结果。

### 问题 2：报告经过 refine 修订，`summary` 应采用什么合并规则？

参考答案：采用覆盖型合并。actor 先写初稿，refine 生成当前修订版后覆盖 `summary`；消息和工具调用轨迹这类连续事件才采用追加型合并。

### 问题 3：`agent → tools → agent` 怎样保证能结束？

参考答案：条件边检查最新模型消息是否包含工具调用；模型给出结论时转到结束节点。同时记录工具调用轮次，达到硬上限时停止循环并生成受控结果。日志记录实际经过的节点，便于检查退出条件。

## 8.3 五阶段基线迁移

### 问题 1：为什么图文件和 OrchestratorService 要分开？

参考答案：图文件定义五个步骤、共享状态和路由；OrchestratorService 保留 NestJS 对外入口，并把图的最终状态映射为已有接口响应。这样现有调用方继续使用相同的 `status`、`usedAgents`、`steps` 和 `report` 字段，图内部可以逐步升级。

### 问题 2：分析与风险并行，汇总怎样等两者都完成？

参考答案：澄清通过后同时进入 analysisStep 与 riskStep，二者分别写 `analysisResult`、`riskResult`。使用等待两个起点的汇合边连接 summaryStep；summary 读取齐备的两份结果并生成报告。

### 问题 3：用户输入太模糊时，本次基线图如何与旧行为保持一致？

参考答案：clarifyStep 把澄清问题写入 `clarificationQuestions`；条件边发现数组有内容就通向 END。OrchestratorService 把该最终状态映射为 `need_clarification`，`usedAgents` 只记录提取与澄清。

## 8.4 入口路由与可信查询

### 问题 1：同一会话上轮分析 Excel，本轮查询一个 REQ 编号，分类节点应读取什么？

参考答案：分类节点读取本轮原始输入 `currentInput`。历史消息仍保存在用于分析的 `enrichedInput` 中；分类依据本轮请求的目标，避免把上轮分析误认为本轮意图。`intent = query` 后，条件边进入查询节点。

### 问题 2：本地缺少需求编号状态表，查询节点如何处理“REQ-20240315-001 的进度”？

参考答案：查询节点明确说明当前系统无法核实该编号状态，同时保留 `queryResponse` 和可持久化的 `report` 文本。具体进度需要接入可信需求数据库或业务接口后才能返回。模型可以组织语言，状态事实由数据源提供。

### 问题 3：怎样判断问候输入跳过了五阶段分析？

参考答案：响应包含 `intent: chat`、`chatResponse`，`usedAgents` 只列分类与闲聊节点，`steps.extract/analysis/risk` 不出现。若接入节点级事件，还可检查实际执行路径为 classifier → chatHandler → END。
