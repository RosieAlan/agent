import {
  Injectable,
  OnModuleDestroy,
} from '@nestjs/common';
import {
  Cron,
  Interval,
} from '@nestjs/schedule';
import type { Response } from 'express';
import { Prisma } from '../generated/prisma/client.js';
import { PrismaService } from '../prisma/prisma.service.js';

export interface TaskEventPayload {
  id: string;
  taskType: string;
  taskId: string;
  status: 'pending' | 'processing' | 'done' | 'error';
  message?: string;
  metadata?: Record<string, unknown>;
  createdAt: string;
}

@Injectable()
export class SseService implements OnModuleDestroy {
  private readonly connections =
    new Map<string, Set<Response>>();

  constructor(
    private readonly prisma: PrismaService,
  ) {}

  addConnection(
    userId: string,
    response: Response,
  ): void {
    if (!this.connections.has(userId)) {
      this.connections.set(userId, new Set());
    }

    this.connections
      .get(userId)!
      .add(response);
  }

  removeConnection(
    userId: string,
    response: Response,
  ): void {
    const userConnections =
      this.connections.get(userId);

    if (!userConnections) return;

    userConnections.delete(response);

    if (userConnections.size === 0) {
      this.connections.delete(userId);
    }
  }

  async emit(
    userId: string,
    event: TaskEventPayload,
  ): Promise<void> {
    try {
      await this.prisma.task_events.create({
        data: {
          id: event.id,
          userId,
          taskType: event.taskType,
          taskId: event.taskId,
          status: event.status,
          message: event.message,
          metadata: event.metadata
            ? event.metadata as Prisma.InputJsonValue
            : undefined,
          createdAt: new Date(event.createdAt),
        },
      });
    } catch (error) {
      console.error(
        '[SseService] 保存任务事件失败：',
        error,
      );
    }

    const userConnections =
      this.connections.get(userId);

    if (!userConnections) return;

    const payload = JSON.stringify(event);

    for (const response of userConnections) {
      if (response.destroyed) {
        userConnections.delete(response);
        continue;
      }

      try {
        response.write(
          `event: task\ndata: ${payload}\n\n`,
        );
      } catch {
        userConnections.delete(response);
      }
    }
  }

  @Interval(5 * 60 * 1000)
  sweepInactiveUsers(): void {
    for (
      const [userId, userConnections]
      of this.connections.entries()
    ) {
      if (userConnections.size === 0) {
        this.connections.delete(userId);
      }
    }
  }

  @Cron('0 3 * * *')
  async cleanupTaskEvents(): Promise<void> {
    const cutoff = new Date(
      Date.now() - 30 * 24 * 60 * 60 * 1000,
    );

    while (true) {
      const deleted =
        await this.prisma.$executeRaw`
          DELETE FROM task_events
          WHERE id IN (
            SELECT id
            FROM task_events
            WHERE "createdAt" < ${cutoff}
            LIMIT 10000
          )
        `;

      if (deleted === 0) break;
    }
  }

  onModuleDestroy(): void {
    for (
      const userConnections
      of this.connections.values()
    ) {
      for (const response of userConnections) {
        response.end();
      }
    }

    this.connections.clear();
  }
}
