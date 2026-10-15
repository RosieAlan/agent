import {
  BaseListChatMessageHistory,
} from '@langchain/core/chat_history';
import {
  BaseMessage,
  HumanMessage,
} from '@langchain/core/messages';
import {
  MessageRole,
} from '../generated/prisma/client.js';
import {
  MessageService,
} from './message.service.js';

export class DbChatHistory
  extends BaseListChatMessageHistory
{
  lc_namespace = ['chat', 'db'];

  constructor(
    private readonly conversationId: string,
    private readonly messageService:
      MessageService,
  ) {
    super();
  }

  async getMessages():
    Promise<BaseMessage[]> {
    return this.messageService
      .getHistoryAsLangChainMessages(
        this.conversationId,
      );
  }

  async addMessage(
    message: BaseMessage,
  ): Promise<void> {
    const role =
      message instanceof HumanMessage
        ? MessageRole.USER
        : MessageRole.ASSISTANT;

    await this.messageService.addMessage(
      this.conversationId,
      role,
      typeof message.content === 'string'
        ? message.content
        : JSON.stringify(message.content),
    );
  }

  async addMessages(
    messages: BaseMessage[],
  ): Promise<void> {
    for (const message of messages) {
      await this.addMessage(message);
    }
  }

  async clear(): Promise<void> {
    await this.messageService.clearHistory(
      this.conversationId,
    );
  }
}
