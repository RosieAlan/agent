import { Injectable } from '@nestjs/common';
import {
  HumanMessage,
  SystemMessage,
  ToolMessage,
  type BaseMessage,
} from '@langchain/core/messages';
import type { StructuredToolInterface } from '@langchain/core/tools';
import { createChatModel } from './model.factory.js';
import { requirementPrompt } from './requirement.prompt-builder.js';
import { requirementChain } from './requirement.chain.js';
import {
  checkConstraintValidityTool,
  lookupEntityDefinitionTool,
} from './tools/basic.tools.js';

const SYSTEM_TEXT = '你是一名需求结构化抽取助手';

@Injectable()
export class LlmService {
  private model = createChatModel();

  async invokeDemo(input: string): Promise<string> {
    const response = await this.model.invoke([
      new SystemMessage(SYSTEM_TEXT),
      new HumanMessage(
        `请从下面文本中抽取 action、constraints、entities：\n${input}`,
      ),
    ]);
    return response.text;
  }

  async streamDemo(input: string, signal?: AbortSignal) {
  return this.model.withConfig({ maxRetries: 0 }).stream([
    new SystemMessage('你是需求分析助手。依据原文输出核心功能、明确约束和待确认事项，最多问3个关键问题。'),
    new HumanMessage(input),
    ], { signal });
  }

  async batchDemo(inputs: string[]): Promise<string[]> {
    const groups = inputs.map((input) => [
      new SystemMessage(SYSTEM_TEXT),
      new HumanMessage(
        `请抽取 action、constraints、entities：\n${input}`,
      ),
    ]);
    const responses = await this.model.batch(groups);
    return responses.map((r) => r.text);
  }

  async promptPreview(input: string) {
    const promptValue = await requirementPrompt.invoke({ input });
    return { rendered: promptValue.toString() };
  }

  async promptToModel(input: string) {
    const messages = await requirementPrompt.formatMessages({
      input,
    });
    const response = await this.model.invoke(messages);
    return { result: response.text };
  }

  async chainInvoke(input: string) {
    const result = await requirementChain.invoke({ input });
    return { result };
  }

  async chainStream(input: string) {
    return requirementChain.stream({ input });
  }

  async chainBatch(inputs: string[]) {
    const results = await requirementChain.batch(
      inputs.map((input) => ({ input })),
    );
    return results.map((result, i) => ({
      index: i + 1,
      result,
    }));
  }

  async toolBindDemo(input: string) {
    const modelWithTools = this.model.bindTools([
      checkConstraintValidityTool,
      lookupEntityDefinitionTool,
    ]);

    const response = await modelWithTools.invoke([
      new SystemMessage(
        '你可以按需要调用工具来校验约束和查询实体定义。',
      ),
      new HumanMessage(`请分析下面需求：${input}`),
    ]);

    return {
      result: response.text,
      toolCalls: response.tool_calls,
    };
  }

  async toolLoopDemo(input: string) {
    const tools: StructuredToolInterface[] = [
      checkConstraintValidityTool,
      lookupEntityDefinitionTool,
    ];
    const toolMap = Object.fromEntries(
      tools.map((t) => [t.name, t]),
    );
    const modelWithTools = this.model.bindTools(tools);

    const messages: BaseMessage[] = [
      new SystemMessage(
        '你可以调用工具来帮助完成需求抽取后的校验。',
      ),
      new HumanMessage(
        `先抽取 action、constraints、entities，再按需要调用工具：${input}`,
      ),
    ];

    const firstResponse = await modelWithTools.invoke(messages);
    messages.push(firstResponse);

    for (const toolCall of firstResponse.tool_calls ?? []) {
      const targetTool = toolMap[toolCall.name];
      if (!targetTool) continue;

      const toolResult = await targetTool.invoke(toolCall.args);
      messages.push(
        new ToolMessage({
          tool_call_id: toolCall.id ?? '',
          content: JSON.stringify(toolResult),
        }),
      );
    }

    const finalResponse = await modelWithTools.invoke(messages);
    return { result: finalResponse.text };
  }
}
