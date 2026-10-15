import { Module } from '@nestjs/common';
import { AuthModule } from '../auth/auth.module.js';
import { AdvancedModule } from '../llm/advanced.module.js';
import { SseModule } from '../sse/sse.module.js';
import { ChunkService } from './chunk.service.js';
import { DocumentController } from './document.controller.js';
import { DocumentService } from './document.service.js';
import { SearchController } from './search.controller.js';
import { SearchService } from './search.service.js';

@Module({
  imports: [AuthModule, AdvancedModule, SseModule],
  controllers: [DocumentController, SearchController],
  providers: [DocumentService, ChunkService, SearchService],
  exports: [DocumentService, ChunkService, SearchService],
})
export class DocumentModule {}
