import {
  Controller,
  Get,
  Req,
  Res,
  UseGuards,
} from '@nestjs/common';
import type {
  Request,
  Response,
} from 'express';
import { JwtAuthGuard } from '../auth/jwt-auth.guard.js';
import { SseService } from './sse.service.js';

@UseGuards(JwtAuthGuard)
@Controller('api/sse')
export class SseController {
  constructor(
    private readonly sseService: SseService,
  ) {}

  @Get('tasks')
  streamTasks(
    @Req() request: Request,
    @Res() response: Response,
  ): void {
    const userId =
      (request.user as any).userId;

    response.setHeader(
      'Content-Type',
      'text/event-stream',
    );
    response.setHeader(
      'Cache-Control',
      'no-cache',
    );
    response.setHeader(
      'Connection',
      'keep-alive',
    );
    response.setHeader(
      'X-Accel-Buffering',
      'no',
    );
    response.flushHeaders();

    response.write(
      `event: connected\ndata: ${
        JSON.stringify({ userId })
      }\n\n`,
    );

    this.sseService.addConnection(
      userId,
      response,
    );

    const heartbeat = setInterval(() => {
      response.write(': heartbeat\n\n');
    }, 30_000);

    request.on('close', () => {
      clearInterval(heartbeat);

      this.sseService.removeConnection(
        userId,
        response,
      );
    });
  }
}
