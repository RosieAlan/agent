import { Module } from '@nestjs/common';
import {
  AgentsController,
  EmbeddingController,
  FilesystemController,
  MemoryController,
} from './advanced.controller.js';
import {
  OrchestratorService,
} from './agents/orchestrator.service.js';
import {
  EmbeddingService,
} from './embedding/embedding.service.js';
import {
  VectorStoreService,
} from './embedding/vector-store.service.js';
import {
  FilesystemService,
} from './filesystem/filesystem.service.js';
import {
  RunnableMemoryService,
} from './memory/runnable-memory.service.js';

@Module({
  providers: [
    RunnableMemoryService,
    FilesystemService,
    EmbeddingService,
    VectorStoreService,
    OrchestratorService,
  ],
  controllers: [
    MemoryController,
    FilesystemController,
    EmbeddingController,
    AgentsController,
  ],
  exports: [
    RunnableMemoryService,
    FilesystemService,
    EmbeddingService,
    VectorStoreService,
    OrchestratorService,
  ],
})
export class AdvancedModule {}
