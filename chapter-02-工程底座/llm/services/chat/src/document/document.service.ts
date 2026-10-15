import {
  BadRequestException,
  ForbiddenException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import { mkdir, unlink, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { PrismaService } from '../prisma/prisma.service.js';
import { ALLOWED_MIME_TYPES } from './document.constants.js';

@Injectable()
export class DocumentService {
  constructor(private readonly prisma: PrismaService) {}

  async upload(
    userId: string,
    file: Express.Multer.File,
    filename: string,
  ) {
    if (!file) throw new BadRequestException('未上传文件');
    if (!ALLOWED_MIME_TYPES.includes(file.mimetype)) {
      throw new BadRequestException(`不支持的文件类型：${file.mimetype}`);
    }

    const safeFilename = path.basename(filename || file.originalname);
    const relativeDir = path.join('uploads', userId);
    const relativePath = path.join(
      relativeDir,
      `${Date.now()}-${safeFilename}`,
    );
    const absoluteDir = path.resolve(process.cwd(), relativeDir);
    const absolutePath = path.resolve(process.cwd(), relativePath);

    await mkdir(absoluteDir, { recursive: true });
    await writeFile(absolutePath, file.buffer);

    try {
      return await this.prisma.documents.create({
        data: {
          userId,
          filename: safeFilename,
          mimeType: file.mimetype,
          size: file.size,
          storageType: 'local',
          filePath: relativePath,
        },
      });
    } catch (error) {
      await unlink(absolutePath).catch(() => undefined);
      throw error;
    }
  }

  async findByUser(userId: string) {
    return this.prisma.documents.findMany({
      where: { userId },
      orderBy: { createdAt: 'desc' },
      include: {
        _count: { select: { document_chunks: true } },
      },
    });
  }

  async findById(documentId: string, userId: string) {
    const document = await this.prisma.documents.findUnique({
      where: { id: documentId },
      include: { document_chunks: true },
    });

    if (!document) throw new NotFoundException('文档不存在');
    if (document.userId !== userId) {
      throw new ForbiddenException('无权访问该文档');
    }

    return document;
  }

  async delete(documentId: string, userId: string) {
    const document = await this.findById(documentId, userId);

    if (document.filePath) {
      const absolutePath = path.resolve(process.cwd(), document.filePath);
      await unlink(absolutePath).catch((error: NodeJS.ErrnoException) => {
        if (error.code !== 'ENOENT') throw error;
      });
    }

    return this.prisma.documents.delete({
      where: { id: documentId },
    });
  }
}
