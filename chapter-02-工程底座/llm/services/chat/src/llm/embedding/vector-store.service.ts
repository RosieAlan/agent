import { Injectable } from '@nestjs/common';
import { MemoryVectorStore } from '@langchain/classic/vectorstores/memory';
import { Document } from '@langchain/core/documents';
import { EmbeddingService } from './embedding.service.js';

@Injectable()
export class VectorStoreService {
  private store: MemoryVectorStore;

  constructor(private readonly embeddings: EmbeddingService) {
    this.store = new MemoryVectorStore(this.embeddings);
  }

  async addTexts(texts: string[]) {
    const docs = texts.map(
      (text) => new Document({ pageContent: text }),
    );
    await this.store.addDocuments(docs);
    return { added: texts.length };
  }

  async search(query: string, k = 3) {
    const results = await this.store.similaritySearchWithScore(
      query,
      k,
    );
    return results.map(([doc, score]) => ({
      content: doc.pageContent,
      score,
    }));
  }
}
