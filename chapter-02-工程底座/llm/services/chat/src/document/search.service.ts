import { Injectable } from '@nestjs/common';
import { Prisma } from '../generated/prisma/client.js';
import { EmbeddingService } from '../llm/embedding/embedding.service.js';
import { PrismaService } from '../prisma/prisma.service.js';

export interface SearchResult {
  chunkId: string;
  documentId: string;
  content: string;
  score: number;
  chunkIndex: number;
}

@Injectable()
export class SearchService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly embedding: EmbeddingService,
  ) {}

  async similaritySearch(
    query: string,
    userId: string,
    topK = 5,
  ): Promise<SearchResult[]> {
    const vector = await this.embedding.embedQuery(query);
    if (!vector.length || !vector.every(Number.isFinite)) {
      throw new Error('EmbeddingService returned an invalid query vector');
    }

    const safeTopK = Math.min(20, Math.max(1, Math.trunc(topK)));
    const vectorLiteral = `[${vector.join(',')}]`;
    const vectorSql = Prisma.raw(`'${vectorLiteral}'::vector`);

    const rows = await this.prisma.$queryRaw<
      Array<{
        chunk_id: string;
        document_id: string;
        content: string;
        score: string | number;
        chunk_index: number;
      }>
    >`
      SELECT
        dc.id AS chunk_id,
        dc."documentId" AS document_id,
        dc.content,
        dc."chunkIndex" AS chunk_index,
        1 - (dc.embedding <=> ${vectorSql}) AS score
      FROM document_chunks dc
      JOIN documents d ON d.id = dc."documentId"
      WHERE d."userId" = ${userId}
        AND dc.embedding IS NOT NULL
      ORDER BY dc.embedding <=> ${vectorSql}
      LIMIT ${safeTopK}
    `;

    return rows.map((row) => ({
      chunkId: row.chunk_id,
      documentId: row.document_id,
      content: row.content,
      score: Number(row.score),
      chunkIndex: row.chunk_index,
    }));
  }
}
