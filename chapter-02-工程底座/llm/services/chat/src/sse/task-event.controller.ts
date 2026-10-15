import {
  Controller,
  Get,
  HttpCode,
  HttpStatus,
  NotFoundException,
  Param,
  Patch,
  Query,
  Req,
  UseGuards,
  UsePipes,
  ValidationPipe,
} from '@nestjs/common';
import type { Request } from 'express';
import { JwtAuthGuard } from '../auth/jwt-auth.guard.js';
import { Prisma } from '../generated/prisma/client.js';
import { PrismaService } from '../prisma/prisma.service.js';
import {
  TaskHistoryQueryDto,
} from './dto/task-history.query.dto.js';
import {
  TaskHistoryResponseDto,
} from './dto/task-event.response.dto.js';

@UseGuards(JwtAuthGuard)
@Controller('api/tasks')
export class TaskEventController {
  constructor(
    private readonly prisma: PrismaService,
  ) {}

  @Get('history')
  @UsePipes(
    new ValidationPipe({
      transform: true,
      whitelist: true,
    }),
  )
  async getHistory(
    @Req() request: Request,
    @Query() query: TaskHistoryQueryDto,
  ): Promise<TaskHistoryResponseDto> {
    const userId =
      (request.user as any).userId;

    const {
      page,
      pageSize,
      taskType,
      startDate,
      endDate,
    } = query;

    const effectiveStart = startDate
      ? new Date(startDate)
      : new Date(
          Date.now()
          - 30 * 24 * 60 * 60 * 1000,
        );

    const effectiveEnd = endDate
      ? new Date(endDate)
      : new Date();

    const where:
      Prisma.task_eventsWhereInput = {
        userId,
        createdAt: {
          gte: effectiveStart,
          lte: effectiveEnd,
        },
      };

    if (taskType) {
      where.taskType = taskType;
    }

    const [items, total] =
      await Promise.all([
        this.prisma.task_events.findMany({
          where,
          orderBy: {
            createdAt: 'desc',
          },
          skip: (page - 1) * pageSize,
          take: pageSize,
        }),
        this.prisma.task_events.count({
          where,
        }),
      ]);

    return {
      items: items.map((event) => ({
        id: event.id,
        taskType: event.taskType,
        taskId: event.taskId,
        status: event.status,
        message:
          event.message ?? undefined,
        metadata:
          event.metadata as
            Record<string, unknown>
            | undefined,
        createdAt:
          event.createdAt.toISOString(),
        readAt:
          event.readAt?.toISOString(),
      })),
      total,
      page,
      pageSize,
      hasMore: page * pageSize < total,
    };
  }

  @Get(':taskId')
  async getByTaskId(
    @Req() request: Request,
    @Param('taskId') taskId: string,
  ) {
    const userId =
      (request.user as any).userId;

    const event =
      await this.prisma.task_events.findFirst({
        where: {
          taskId,
          userId,
        },
        orderBy: {
          createdAt: 'desc',
        },
      });

    if (!event) {
      throw new NotFoundException(
        '任务不存在',
      );
    }

    return {
      id: event.id,
      taskType: event.taskType,
      taskId: event.taskId,
      status: event.status,
      message: event.message ?? undefined,
      metadata: event.metadata ?? undefined,
      createdAt:
        event.createdAt.toISOString(),
      readAt:
        event.readAt?.toISOString(),
    };
  }

  @Patch(':taskId/read')
  @HttpCode(HttpStatus.OK)
  async markRead(
    @Req() request: Request,
    @Param('taskId') taskId: string,
  ) {
    const userId =
      (request.user as any).userId;
    const readAt = new Date();

    const updated =
      await this.prisma.task_events.updateMany({
        where: {
          taskId,
          userId,
          readAt: null,
        },
        data: {
          readAt,
        },
      });

    if (updated.count === 0) {
      throw new NotFoundException(
        '任务不存在或已读',
      );
    }

    return {
      readAt: readAt.toISOString(),
    };
  }
}
