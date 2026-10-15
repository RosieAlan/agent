import { Injectable } from '@nestjs/common';
import type {
  BaseMessage,
} from '@langchain/core/messages';
import {
  ChatPromptTemplate,
  MessagesPlaceholder,
} from '@langchain/core/prompts';
import {
  createChatModel,
} from '../model.factory.js';
import {
  aiUIResponseSchema,
} from './ui-schemas.js';
import type {
  AIUIResponse,
} from './ui-types.js';

const UI_SYSTEM_PROMPT = `
你是一名需求分析助手。请只输出符合 UI 协议的 JSON 对象。

组件选择规则：
- selection：用户需要从明确选项中选择。
- form：用户需要填写多个字段。
- confirmation：用户需要确认重要操作。
- card：展示已有的结构化信息。
- steps：展示流程进度。
- table：展示多条结构化记录。
- action_buttons：提供下一步操作。
- text：解释说明或普通回复。

message 必须有内容，components 可以包含多个组件。
所有字段名称必须符合给定 Schema。

用户说“我要提一个新需求”时，
返回一个 selection，
提供 functional、performance、
security、ui_ux 四个选项。
selection.options 中每个选项必须使用 id 和 label 字段；
id 分别为 functional、performance、security、ui_ux。
selection 必须包含 title 字段，固定填写“请选择需求类型”。
四个选项的 id 和 label 分别是：functional / 功能需求、performance / 性能需求、security / 安全需求、ui_ux / UI/UX 需求。

展示需求详情时，只使用输入上下文中的事实。
缺少可信详情时，引导用户提供需求编号或数据。
`;

@Injectable()
export class UIResponseService {
  private readonly model = createChatModel();

  private readonly structuredModel =
    this.model.withStructuredOutput(
      aiUIResponseSchema,
      { method: 'jsonMode' },
    );

  private readonly prompt =
    ChatPromptTemplate.fromMessages([
      ['system', UI_SYSTEM_PROMPT],
      new MessagesPlaceholder('history'),
      ['human', '{input}'],
    ]);

  private readonly chain =
    this.prompt.pipe(this.structuredModel);

  async generateUIResponse(
    input: string,
    history: BaseMessage[] = [],
    context?: Record<string, unknown>,
  ): Promise<AIUIResponse> {
    const enrichedInput = context
      ? `${input}\n\n当前上下文：${JSON.stringify(context)}`
      : input;

    const result = await this.chain.invoke({
      input: enrichedInput,
      history,
    });

    return aiUIResponseSchema.parse(result);
  }
}
