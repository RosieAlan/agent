import { createChatModel } from '../model.factory.js';
import { trackAnalysis, type AnalysisRunOptions } from '../analysis-progress.js';
import {
  createAnalysisSupervisorSubGraph,
  outputFields,
} from './analysis-supervisor.js';
import type { ExpertName } from './experts.js';
import type { RunnableConfig } from
  '@langchain/core/runnables';
import {
  Annotation,
  END,
  MessagesAnnotation,
  START,
  StateGraph,
} from '@langchain/langgraph';
import {
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
  activeExperts: Annotation<ExpertName[]>(),
  expertAnalyses:
    Annotation<Partial<Record<ExpertName, string>>>(),

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
  config: RunnableConfig,
) {
  const extractResult = await extractAgent.invoke({
    input: state.input,
  }, config);

  return { extractResult };
}

async function clarifyStep(
  state: typeof RequirementAnalysisState.State,
  config: RunnableConfig,
) {
  const clarifyRaw = await clarifyAgent.invoke({
    input: state.input,
    extractResult: state.extractResult,
  }, config);

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
  config: RunnableConfig,
  options: AnalysisRunOptions,
) {
  const graph = createAnalysisSupervisorSubGraph(
    createChatModel(),
    options,
  );

  const result = await graph.invoke({
    input: state.input,
    extractResult: state.extractResult,
    retrievedContext: state.retrievedContext,
  }, config);

  const expertAnalyses = Object.fromEntries(
    result.activeExperts.map((name) => [
      name,
      result[outputFields[name]],
    ]),
  ) as Partial<Record<ExpertName, string>>;

  return {
    analysisResult: result.analysisResult,
    activeExperts: result.activeExperts,
    expertAnalyses,
  };
}

async function riskStep(
  state: typeof RequirementAnalysisState.State,
  config: RunnableConfig,
) {
  const riskResult = await riskAgent.invoke({
    input: state.input,
    extractResult: state.extractResult,
  }, config);

  return { riskResult };
}

async function summaryStep(
  state: typeof RequirementAnalysisState.State,
  config: RunnableConfig,
) {
  const report = await summaryAgent.invoke({
    input: state.input,
    extractResult: state.extractResult,
    analysisResult: state.analysisResult,
    riskResult: state.riskResult,
    retrievedContext: state.retrievedContext,
  }, config);

  return { report };
}

export function createAnalysisGraph(options: AnalysisRunOptions = {}) {
  type State = typeof RequirementAnalysisState.State;
  const tracked = (
    step: string,
    label: string,
    run: (state: State, config: RunnableConfig) => Promise<Partial<State>>,
  ) => (state: State, config: RunnableConfig) =>
    trackAnalysis(options, step, label, () => run(state, config));
  return new StateGraph(RequirementAnalysisState)
    .addNode('extractStep', tracked('extract', '提取需求', extractStep))
    .addNode('clarifyStep', tracked('clarify', '检查需求完整性', clarifyStep))
    .addNode('analysisStep', tracked('analysis', '专家协作分析', (s, c) => analysisStep(s, c, options)))
    .addNode('riskStep', tracked('risk', '评估风险', riskStep))
    .addNode('summaryStep', tracked('summary', '生成分析报告', summaryStep))
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
  options: AnalysisRunOptions = {},
) {
  return createAnalysisGraph(options).invoke({
    input,
    retrievedContext,
    messages: [],
  }, { signal: options.signal });
}
