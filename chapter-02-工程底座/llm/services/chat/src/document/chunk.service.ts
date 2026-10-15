import {
  BadRequestException,
  ForbiddenException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import { RecursiveCharacterTextSplitter } from '@langchain/textsplitters';
import { v4 as uuid } from 'uuid';
import { Prisma } from '../generated/prisma/client.js';
import { EmbeddingService } from '../llm/embedding/embedding.service.js';
import { PrismaService } from '../prisma/prisma.service.js';
import { SseService } from '../sse/sse.service.js';
import { extractText } from './parsers/parser.factory.js';

@Injectable()
export class ChunkService {
  private readonly splitter = new RecursiveCharacterTextSplitter({
    chunkSize: 500,
    chunkOverlap: 50,
  });

  constructor(
    private readonly prisma: PrismaService,
    private readonly embedding: EmbeddingService,
    private readonly sseService: SseService,
  ) {}

  async processDocument(documentId: string, userId: string): Promise<void> {
    const document = await this.prisma.documents.findUnique({
      where: {
        id: documentId,
      },
    });

    if (!document) {
      throw new NotFoundException('文档不存在');
    }

    if (document.userId !== userId) {
      throw new ForbiddenException('无权处理该文档');
    }

    if (!document.filePath) {
      throw new NotFoundException('文档文件路径不存在');
    }

    await this.prisma.documents.update({
      where: {
        id: documentId,
      },
      data: {
        status: 'processing',
      },
    });

    await this.sseService.emit(userId, {
      id: uuid(),
      taskType: 'document_vectorize',
      taskId: documentId,
      status: 'processing',
      message: '开始解析和向量化文档',
      createdAt: new Date().toISOString(),
    });

    try {
      const text = await extractText(document.filePath, document.mimeType);

      if (!text.trim()) {
        throw new BadRequestException('文档内容为空');
      }

      const chunks = await this.splitter.splitText(text);

      await this.prisma.document_chunks.deleteMany({
        where: {
          documentId,
        },
      });

      const vectors = await this.embedding.embedDocuments(chunks);

      if (vectors.length !== chunks.length) {
        throw new Error('向量数量与分块数量不一致');
      }

      for (let index = 0; index < chunks.length; index += 1) {
        const created = await this.prisma.document_chunks.create({
          data: {
            documentId,
            content: chunks[index],
            chunkIndex: index,
          },
        });

        const vectorLiteral = `[${vectors[index].join(',')}]`;

        const vectorSql = Prisma.raw(`'${vectorLiteral}'::vector`);

        await this.prisma.$executeRaw`
          UPDATE document_chunks
          SET embedding = ${vectorSql}
          WHERE id = ${created.id}
        `;
      }

      await this.prisma.documents.update({
        where: {
          id: documentId,
        },
        data: {
          status: 'done',
          chunkCount: chunks.length,
        },
      });

      await this.sseService.emit(userId, {
        id: uuid(),
        taskType: 'document_vectorize',
        taskId: documentId,
        status: 'done',
        message: `向量化完成，共 ${chunks.length} 个 Chunk`,
        metadata: {
          chunkCount: chunks.length,
        },
        createdAt: new Date().toISOString(),
      });
    } catch (error) {
      await this.prisma.documents.update({
        where: {
          id: documentId,
        },
        data: {
          status: 'error',
        },
      });

      await this.sseService.emit(userId, {
        id: uuid(),
        taskType: 'document_vectorize',
        taskId: documentId,
        status: 'error',
        message: error instanceof Error ? error.message : '文档处理失败',
        createdAt: new Date().toISOString(),
      });

      throw error;
    }
  }
}
