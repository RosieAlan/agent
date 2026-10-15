import {
  Body,
  BadRequestException,
  Controller,
  Delete,
  Get,
  HttpCode,
  HttpStatus,
  Param,
  Post,
  Query,
  Req,
  Res,
  UseGuards,
} from '@nestjs/common';
import type { Request, Response } from 'express';
import {
  JwtAuthGuard,
} from '../auth/jwt-auth.guard.js';
import {
  AdvancedAnalysisService,
} from '../llm/advanced-analysis.service.js';
import {
  MessageService,
} from '../message/message.service.js';
import {
  ConversationService,
} from './conversation.service.js';

@UseGuards(JwtAuthGuard)
@Controller('api/conversations')
export class ConversationController {
  constructor(
    private readonly conversationService:
      ConversationService,
    private readonly messageService:
      MessageService,
    private readonly advancedAnalysis:
      AdvancedAnalysisService,
  ) {}

  @Post()
  async create(
    @Req() request: Request,
    @Body()
    body: {
      title?: string;
    },
  ) {
    const userId =
      (request.user as any).userId;

    return this.conversationService
      .create(
        userId,
        body?.title,
      );
  }

  @Get()
  async findAll(
    @Req() request: Request,
  ) {
    const userId =
      (request.user as any).userId;

    return this.conversationService
      .findByUser(userId);
  }

  @Get(':id/messages')
  async getMessages(
    @Req() request: Request,
    @Param('id') id: string,
    @Query('limit') limit?: string,
  ) {
    const userId =
      (request.user as any).userId;

    await this.conversationService
      .findById(id, userId);

    const parsed = limit
      ? parseInt(limit, 10)
      : undefined;

    const safeLimit =
      parsed
      && Number.isFinite(parsed)
      && parsed > 0
        ? parsed
        : undefined;

    return this.messageService
      .getHistory(
        id,
        safeLimit,
      );
  }

  @Post(':id/chat')
  async chat(
    @Req() request: Request,
    @Param('id') id: string,
    @Body()
    body: {
      input: string;
    },
  ) {
    const userId =
      (request.user as any).userId;

    await this.conversationService
      .findById(id, userId);

    return this.advancedAnalysis
      .analyze(
        userId,
        id,
        body.input,
      );
  }

  @Post(':id/chat/stream')
  async streamChat(
    @Req() request: Request,
    @Param('id') id: string,
    @Body() body: { input: string },
    @Res() response: Response,
  ) {
    if (typeof body?.input !== 'string' || !body.input.trim()) {
      throw new BadRequestException('请输入需求内容');
    }
    const userId = (request.user as any).userId;
    await this.conversationService.findById(id, userId);

    response.setHeader('Content-Type', 'text/event-stream; charset=utf-8');
    response.setHeader('Cache-Control', 'no-cache, no-transform');
    response.setHeader('X-Accel-Buffering', 'no');
    response.flushHeaders();

    const abort = new AbortController();
    const send = (event: string, data: unknown) => {
      if (!response.writableEnded && !response.destroyed) {
        response.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
      }
    };
    const disconnected = () => abort.abort(new Error('客户端已断开连接'));
    response.on('close', disconnected);
    const heartbeat = setInterval(() => {
      if (!response.writableEnded && !response.destroyed) response.write(': heartbeat\n\n');
    }, 10_000);
    const deadline = setTimeout(() => {
      abort.abort(new Error('分析超过10分钟，请稍后重试或缩小需求范围'));
    }, 600_000);

    try {
      send('progress', { step: 'start', label: '已接收需求', status: 'completed' });
      const result = await this.advancedAnalysis.analyze(userId, id, body.input, {
        signal: abort.signal,
        onProgress: (event) => send('progress', event),
      });
      send('done', result);
    } catch (error) {
      send('error', {
        message: error instanceof Error ? error.message : '分析失败，请稍后重试',
      });
    } finally {
      clearInterval(heartbeat);
      clearTimeout(deadline);
      response.off('close', disconnected);
      if (!response.writableEnded && !response.destroyed) response.end();
    }
  }

  @Delete(':id')
  @HttpCode(HttpStatus.NO_CONTENT)
  async remove(
    @Req() request: Request,
    @Param('id') id: string,
  ) {
    const userId =
      (request.user as any).userId;

    await this.conversationService
      .delete(
        id,
        userId,
      );
  }
}
