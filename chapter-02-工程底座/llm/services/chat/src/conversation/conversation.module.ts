import { Module } from '@nestjs/common';
import { AuthModule } from '../auth/auth.module.js';
import { DocumentModule } from '../document/document.module.js';
import { AdvancedAnalysisService } from '../llm/advanced-analysis.service.js';
import { AdvancedModule } from '../llm/advanced.module.js';
import { MessageModule } from '../message/message.module.js';
import { ConversationController } from './conversation.controller.js';
import { ConversationService } from './conversation.service.js';

@Module({
  imports: [
    AuthModule,
    MessageModule,
    AdvancedModule,
    DocumentModule,
  ],
  providers: [
    ConversationService,
    AdvancedAnalysisService,
  ],
  controllers: [ConversationController],
  exports: [ConversationService],
})
export class ConversationModule {}
