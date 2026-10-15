import { Body, Controller, Delete, Get, Param, Post } from '@nestjs/common';
import { EmbeddingService } from './embedding/embedding.service.js';
import { VectorStoreService } from './embedding/vector-store.service.js';
import { FilesystemService } from './filesystem/filesystem.service.js';
import { RunnableMemoryService } from './memory/runnable-memory.service.js';
import { OrchestratorService } from './agents/orchestrator.service.js';

@Controller('api/memory')
export class MemoryController {
  constructor(private readonly memory: RunnableMemoryService) {}

  @Post('chat')
  async chat(
    @Body()
    body: {
      sessionId: string;
      input: string;
    },
  ) {
    return this.memory.chat(body.sessionId, body.input);
  }

  @Get('history/:sessionId')
  async history(
    @Param('sessionId')
    sessionId: string,
  ) {
    const messages = await this.memory.getHistory(sessionId);

    return messages.map((message) => ({
      type: message.type,
      content: message.text,
    }));
  }

  @Delete('history/:sessionId')
  clear(
    @Param('sessionId')
    sessionId: string,
  ) {
    this.memory.clearSession(sessionId);

    return {
      cleared: sessionId,
    };
  }
}

@Controller('api/files')
export class FilesystemController {
  constructor(private readonly filesystem: FilesystemService) {}

  @Post('chat')
  async chat(
    @Body()
    body: {
      input: string;
    },
  ) {
    return this.filesystem.chat(body.input);
  }
}

@Controller('api/embedding')
export class EmbeddingController {
  constructor(
    private readonly embedding: EmbeddingService,
    private readonly vectorStore: VectorStoreService,
  ) {}

  @Post('embed')
  async embed(
    @Body()
    body: {
      text: string;
    },
  ) {
    const vector = await this.embedding.embedQuery(body.text);

    return {
      dimension: vector.length,
      vector,
    };
  }

  @Post('store')
  async store(
    @Body()
    body: {
      texts: string[];
    },
  ) {
    return this.vectorStore.addTexts(body.texts);
  }

  @Post('search')
  async search(
    @Body()
    body: {
      query: string;
      k?: number;
    },
  ) {
    return this.vectorStore.search(body.query, body.k);
  }
}

@Controller('api/agents')
export class AgentsController {
  constructor(private readonly orchestrator: OrchestratorService) {}

  @Post('orchestrate')
  async orchestrate(
    @Body()
    body: {
      input: string;
    },
  ) {
    return this.orchestrator.orchestrate(body.input);
  }
}
