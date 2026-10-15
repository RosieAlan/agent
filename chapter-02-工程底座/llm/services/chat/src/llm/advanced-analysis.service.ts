import { Injectable } from '@nestjs/common';
import { trackAnalysis, type AnalysisRunOptions } from './analysis-progress.js';
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
    options: AnalysisRunOptions = {},
  ) {
    const history =
      new DbChatHistory(
        conversationId,
        this.messageService,
      );

    const messages =
      await history.getMessages();

    options.signal?.throwIfAborted();

    let retrievedDocuments:
      Awaited<
        ReturnType<
          SearchService['similaritySearch']
        >
      > = [];

    try {
      retrievedDocuments = await trackAnalysis(options, 'retrieval', '检索参考文档', () => this.searchService
          .similaritySearch(
            input,
            userId,
            3,
          ));
    } catch (error) {
      options.signal?.throwIfAborted();
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

    await this.messageService.addMessage(
      conversationId,
      MessageRole.USER,
      input,
    );

    const result = await this.orchestrator.orchestrate(
      enrichedInput, retrievedContext, options,
    );
    options.signal?.throwIfAborted();

    await this.messageService.addMessage(
        conversationId,
        MessageRole.ASSISTANT,
        result.status === 'need_clarification'
          ? result.clarificationQuestions.join('\n')
          : result.report ?? '分析未完成',
        {
          status: result.status,
          activeExperts: 'activeExperts' in result ? result.activeExperts : [],
          expertAnalyses: 'expertAnalyses' in result ? result.expertAnalyses : {},
          usedAgents:
            result.usedAgents,
          retrievedDocuments:
            retrievedDocuments.length,
        },
      );

    return {
      ...result,
      retrievedDocuments:
        retrievedDocuments.map(
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
