import {
  Annotation,
  END,
  START,
  StateGraph,
} from '@langchain/langgraph';
import { BaseChatModel } from
  '@langchain/core/language_models/chat_models';
import {
  HumanMessage,
  SystemMessage,
} from '@langchain/core/messages';
import type { RunnableConfig } from
  '@langchain/core/runnables';
import { z } from 'zod';
import { trackAnalysis, type AnalysisRunOptions } from '../analysis-progress.js';
import {
  createExpertSubGraph,
  expertNames,
  type ExpertName,
} from './experts.js';

const SelectionSchema = z.object({
  experts: z.array(z.enum(expertNames)).min(1).max(4),
});

const AnalysisState = Annotation.Root({
  input: Annotation<string>(),
  extractResult: Annotation<string>(),
  retrievedContext: Annotation<string>(),
  activeExperts: Annotation<ExpertName[]>(),

  functionalAnalysis: Annotation<string>(),
  performanceAnalysis: Annotation<string>(),
  securityAnalysis: Annotation<string>(),
  complianceAnalysis: Annotation<string>(),

  analysisResult: Annotation<string>(),
});

export const outputFields = {
  functional: 'functionalAnalysis',
  performance: 'performanceAnalysis',
  security: 'securityAnalysis',
  compliance: 'complianceAnalysis',
} as const;

export function createAnalysisSupervisorSubGraph(
  model: BaseChatModel,
  options: AnalysisRunOptions = {},
) {
  const selector = model.withStructuredOutput(
    SelectionSchema,
    { method: 'jsonMode' },
  );

  async function supervisor(
    state: typeof AnalysisState.State,
    config: RunnableConfig,
  ) {
    const raw = await selector.invoke([
      new SystemMessage([
        '返回JSON，包含experts数组，选择参与需求分析的专家。',
        'functional：功能流程和验收，每次选择。',
        'performance：大批量、并发、耗时、吞吐量。',
        'security：登录、权限、上传文件、敏感数据。',
        'compliance：个人信息、数据保留或明确合规约束。',
        '只调整按钮文案时选择functional。',
      ].join('\n')),

      new HumanMessage(JSON.stringify({
        input: state.input,
        extracted: state.extractResult,
      })),
    ], config);

    const selected = SelectionSchema.parse(raw);

    return {
      activeExperts: [...new Set<ExpertName>([
        'functional',
        ...selected.experts,
      ])],
    };
  }

  function expertNode(name: ExpertName) {
    return async (
      state: typeof AnalysisState.State,
      config: RunnableConfig,
    ) => {
      const graph = createExpertSubGraph(
        name,
        model,
        state.retrievedContext,
      );

      const result = await trackAnalysis(options, `${name}Expert`, {
        functional: '功能专家', performance: '性能专家',
        security: '安全专家', compliance: '合规专家',
      }[name], () => graph.invoke({
        messages: [new HumanMessage(JSON.stringify({
          input: state.input,
          extracted: state.extractResult,
        }))],
        toolRounds: 0,
      }, config));

      return {
        [outputFields[name]]: result.report,
      };
    };
  }

  function aggregate(state: typeof AnalysisState.State) {
    const analysisResult = state.activeExperts
      .map((name) => {
        const report = state[outputFields[name]];

        if (!report) {
          throw new Error(`${name}专家结果缺失`);
        }

        return `## ${name}\n${report}`;
      })
      .join('\n\n');

    return { analysisResult };
  }

  return new StateGraph(AnalysisState)
    .addNode('supervisor', (state, config) =>
      trackAnalysis(options, 'supervisor', '选择参与专家', () => supervisor(state, config)))
    .addNode('functional', expertNode('functional'))
    .addNode('performance', expertNode('performance'))
    .addNode('security', expertNode('security'))
    .addNode('compliance', expertNode('compliance'))
    .addNode('aggregator', aggregate)
    .addEdge(START, 'supervisor')
    .addConditionalEdges(
      'supervisor',
      (state) => state.activeExperts,
    )
    .addEdge('functional', 'aggregator')
    .addEdge('performance', 'aggregator')
    .addEdge('security', 'aggregator')
    .addEdge('compliance', 'aggregator')
    .addEdge('aggregator', END)
    .compile();
}
