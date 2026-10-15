import { Module } from '@nestjs/common';
import { ScheduleModule } from '@nestjs/schedule';
import { AppController } from './app.controller.js';
import { AppService } from './app.service.js';
import { AuthModule } from './auth/auth.module.js';
import { ConversationModule } from './conversation/conversation.module.js';
import { DocumentModule } from './document/document.module.js';
import { AdvancedModule } from './llm/advanced.module.js';
import { LlmModule } from './llm/llm.module.js';
import { MessageModule } from './message/message.module.js';
import { PrismaModule } from './prisma/prisma.module.js';
import { SseModule } from './sse/sse.module.js';
import {
  UiChatModule,
} from './llm/ui-protocol/ui-chat.module.js';

@Module({
  imports: [
    ScheduleModule.forRoot(),
    PrismaModule,
    AuthModule,
    LlmModule,
    AdvancedModule,
    MessageModule,
    ConversationModule,
    SseModule,
    DocumentModule,
    UiChatModule,
  ],
  controllers: [AppController],
  providers: [AppService],
})
export class AppModule {}
