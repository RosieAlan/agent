import { Injectable } from '@nestjs/common';
import {
  AIMessage,
  BaseMessage,
  HumanMessage,
} from '@langchain/core/messages';
import {
  MessageRole,
  Prisma,
} from '../generated/prisma/client.js';
import { PrismaService } from '../prisma/prisma.service.js';

@Injectable()
export class MessageService {
  constructor(
    private readonly prisma: PrismaService,
  ) {}

  async addMessage(
    conversationId: string,
    role: MessageRole,
    content: string,
    metadata?: Record<string, unknown>,
  ) {
    return this.prisma.messages.create({
      data: {
        conversationId,
        role,
        content,
        metadata:
          metadata as Prisma.InputJsonValue,
      },
    });
  }

  async getHistory(
    conversationId: string,
    limit?: number,
  ) {
    return this.prisma.messages.findMany({
      where: { conversationId },
      orderBy: { createdAt: 'asc' },
      ...(limit ? { take: limit } : {}),
    });
  }

  async getHistoryAsLangChainMessages(
    conversationId: string,
  ): Promise<BaseMessage[]> {
    const messages =
      await this.getHistory(conversationId);

    return messages.map((message) =>
      message.role === MessageRole.USER
        ? new HumanMessage(message.content)
        : new AIMessage(message.content),
    );
  }

  async clearHistory(
    conversationId: string,
  ) {
    await this.prisma.messages.deleteMany({
      where: { conversationId },
    });
  }
}
