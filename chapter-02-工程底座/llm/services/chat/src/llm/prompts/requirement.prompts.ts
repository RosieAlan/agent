import { ChatPromptTemplate } from '@langchain/core/prompts';

export const extractPrompt = ChatPromptTemplate.fromMessages([
  [
    'system',
    `你是需求抽取 Agent，负责从用户描述中抽取结构化需求字段。

只输出一个 JSON 对象，不要输出任何其他文字，格式如下：
{{
  "requirementType": "功能需求 / 非功能需求 / 缺陷 / 其他",
  "coreFeature": "核心功能，一句话",
  "targetUsers": ["目标用户"],
  "businessGoal": "业务目标",
  "constraints": ["约束条件"],
  "priority": "P0 / P1 / P2 / 未知",
  "isComplete": true,
  "missingFields": ["缺失的字段名"]
}}

规则：
1. 只根据原文抽取，不编造
2. 原文没有的字段，字符串写 ""，数组写 []，并把字段名写进 missingFields
3. coreFeature 或 targetUsers 缺失时，isComplete 为 false`,
  ],
  ['human', '需求描述：{input}'],
]);

export const clarifyPrompt = ChatPromptTemplate.fromMessages([
  [
    'system',
    `你是需求澄清 Agent，负责判断是否需要向用户追问。

判断规则：
1. 只有"核心功能"或"目标用户"为空、或者无法确定时，才需要澄清
2. 其他字段缺失不需要澄清，留给后续分析环节处理

只输出一个 JSON 对象，不要输出任何其他文字：
{{"needsClarification": true 或 false, "questions": ["要问用户的问题"]}}

不需要澄清时 questions 为 []。最多列 3 个问题。`,
  ],
  ['human', '原始需求：{input}\n\n抽取结果：{extractResult}'],
]);

export const analysisPrompt = ChatPromptTemplate.fromMessages([
  [
    'system',
    `你是需求分析 Agent，负责对需求做多维度分析。

用 Markdown 输出以下小节，每节 2 到 4 条要点，总长度不超过 400 字：
## 功能分解
## 用户故事
## 验收标准
## 依赖
## 建议`,
  ],
  ['human', '原始需求：{input}\n\n结构化字段：{extractResult}'],
]);

export const riskPrompt = ChatPromptTemplate.fromMessages([
  [
    'system',
    `你是需求风险评估 Agent，负责识别需求中的风险。

用 Markdown 输出以下小节，每条风险标注等级（高 / 中 / 低），总长度不超过 300 字：
## 模糊性风险
## 范围风险
## 技术风险
## 业务风险`,
  ],
  ['human', '原始需求：{input}\n\n结构化字段：{extractResult}'],
]);

export const summaryPrompt = ChatPromptTemplate.fromMessages([
  [
    'system',
    `你是需求报告汇总 Agent，负责把各 Agent 的结果整合成一份需求分析报告。

用 Markdown 输出，结构如下，总长度不超过 500 字：
# 需求分析报告
## 需求概述
## 完整性结论
## 关键分析
## 主要风险
## 参考资料
## 下一步建议

规则：只使用输入中已有的信息，不编造。`,
  ],
  [
    'human',
    `原始需求：{input}

结构化字段：{extractResult}

需求分析：{analysisResult}

风险评估：{riskResult}

参考资料：{retrievedContext}`,
  ],
]);
