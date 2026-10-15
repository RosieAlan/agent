import { Module } from '@nestjs/common';
import { AuthModule } from '../auth/auth.module.js';
import { PrismaModule } from '../prisma/prisma.module.js';
import { SseController } from './sse.controller.js';
import { SseService } from './sse.service.js';
import {
  TaskEventController,
} from './task-event.controller.js';

@Module({
  imports: [
    PrismaModule,
    AuthModule,
  ],
  providers: [
    SseService,
  ],
  controllers: [
    SseController,
    TaskEventController,
  ],
  exports: [
    SseService,
  ],
})
export class SseModule {}
