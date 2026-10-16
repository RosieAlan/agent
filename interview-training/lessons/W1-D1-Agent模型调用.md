# W1-D1 第一块：服务端模型调用

2026-10-15 用户授权提前开始，正式起始日仍为10月16日。对应原第一章1.2、第三章模型调用与提示模板；岗位：模型接入、Prompt、服务端调试。检查点C01-1/C01-2/C03-1本次开始学习，待独立验收。

目标：必背模型、调用客户端、Prompt、messages及invoke职责；会用现有工厂完成一次提取；了解完整调用结果与文本、业务校验的区别。

项目已核对：services/chat/src/llm/model.factory.ts 的createChatModel读取YAML中的model/temperature/maxTokens，读取环境中的OPENAI_API_KEY/OPENAI_BASE_URL，创建本地调用客户端；invoke调用供应商。load-env.ts根据工作目录加载.env，因此从services/chat运行练习。创建调用客户端与训练模型分别是不同操作。

messages组织示例：system负责抽取任务、缺失信息处理、输出要求；user放原始需求；模型响应在LangChain中为AI消息。response.text取得文本，可用时usage_metadata提供用量。Prompt约定的JSON通过后续解析与Schema进一步校验；本块观察原始文本。

独立练习由学生手动创建：interview-training/labs/w1-d1/prompts.ts保存抽取规则；model-call.ts复用项目load-env与model.factory，组织system/user消息、调用invoke并打印文本。项目业务源码和现有服务保留。脚本完整文本以本次对话教学为准。运行目录services/chat，命令bun run ../../../../interview-training/labs/w1-d1/model-call.ts。该脚本发起一次真实上游请求，运行结果由学生提交。

Prompt要求：抽取核心功能、明确约束、缺失信息三小节；遵守已知事实，缺失信息标待确认；输入默认“企业管理员需要批量导入Excel，最多一万行，错误行可以导出”。预期包括Excel批量导入、一万行和错误行导出，优先级等未提供内容标待确认。缺失项数量及措辞允许变化。

作业：A提交第一次调用输出；B把输入改为“需要导入Excel”，仅改输入，比较两次缺失信息和模型有无编造，解释system与user各自作用；C模型调用出现404时，列出模型ID、baseURL与协议/接口路径的排查顺序和脱敏证据，结合此前实际错误说明。

面试答案1：调用客户端封装供应商请求、鉴权和响应转换，Prompt定义任务、规则和输出要求，messages组织角色与上下文，invoke执行调用并取得模型消息。工厂集中配置用于保持凭据、地址和协议兼容策略一致。

面试答案2：system承载开发者设定的行为与任务规则，user承载当前输入，assistant表示模型回复；历史消息由应用选择加入调用。角色分工有助于组织上下文，可靠性和权限仍依赖应用校验。

检查题：① 改最大行数是改user输入还是工厂；② 同模型、换输入为何仍执行相同抽取任务；③ 输出自行写P0时怎样判断及处理。答案：①user；②system里任务规则保持；③核对原文，识别无依据内容，改进Prompt并用样例回归，后续增加结构化与事实校验。

验收：能跑一次调用、能解释四个职责、能独立改输入并比较结果；日志与截图隐藏完整密钥/令牌。阅读已完成，调用与掌握待提交。

官方核对：2026-10-15 [Models](https://docs.langchain.com/oss/javascript/langchain/models)、[Messages](https://docs.langchain.com/oss/javascript/langchain/messages)。示例采用本地安装及既有工厂写法，未执行真实模型调用。
