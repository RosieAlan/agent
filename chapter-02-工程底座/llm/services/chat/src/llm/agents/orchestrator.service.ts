import { Injectable } from '@nestjs/common';
import type { AnalysisRunOptions } from '../analysis-progress.js';
import { runAnalysisGraph } from
  '../graph/requirement-analysis-graph.js';

@Injectable()
export class OrchestratorService {
  async orchestrate(
    input: string,
    retrievedContext = '无相关参考文档',
    options: AnalysisRunOptions = {},
  ) {
    try {
      const result = await runAnalysisGraph(
        input,
        retrievedContext,
        options,
      );

      if (result.clarificationQuestions.length > 0) {
        return {
          mode: 'supervisor_workflow',
          status: 'need_clarification' as const,
          clarificationQuestions:
            result.clarificationQuestions,
          usedAgents: ['extractAgent', 'clarifyAgent'],
          fallback: 'ask_user',
        };
      }

      return {
        mode: 'supervisor_workflow',
        status: 'completed' as const,
        clarificationQuestions: [],
        usedAgents: [
          'extractAgent',
          'clarifyAgent',
          'supervisor',
          ...result.activeExperts.map(
            (name) => `${name}Expert`,
          ),
          'riskAgent',
          'summaryAgent',
        ],

        activeExperts: result.activeExperts,
        expertAnalyses: result.expertAnalyses,

        fallback: null,
        steps: {
          extract: result.extractResult,
          analysis: result.analysisResult,
          risk: result.riskResult,
        },
        report: result.report,
      };
    } catch (error) {
      options.signal?.throwIfAborted();
      return {
        mode: 'supervisor_workflow',
        status: 'failed' as const,
        clarificationQuestions: [],
        usedAgents: [],
        fallback: 'manual_review',
        report: '分析流程失败，请转人工复核。',
        error: String(error),
      };
    }
  }
}
