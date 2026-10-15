import {
  BadRequestException,
  Controller,
  Delete,
  Get,
  HttpCode,
  HttpStatus,
  Param,
  Post,
  Req,
  UploadedFile,
  UseGuards,
  UseInterceptors,
} from '@nestjs/common';
import { FileInterceptor } from '@nestjs/platform-express';
import type { Request } from 'express';
import { memoryStorage } from 'multer';
import { JwtAuthGuard } from '../auth/jwt-auth.guard.js';
import {
  ALLOWED_MIME_TYPES,
  MAX_FILE_SIZE,
} from './document.constants.js';
import { DocumentService } from './document.service.js';
import { ChunkService } from './chunk.service.js';

@UseGuards(JwtAuthGuard)
@Controller('api/documents')
export class DocumentController {
  constructor(
    private readonly documentService: DocumentService,
    private readonly chunkService: ChunkService,
  ) {}

  @Post('upload')
  @UseInterceptors(
    FileInterceptor('file', {
      storage: memoryStorage(),
      limits: { fileSize: MAX_FILE_SIZE },
      fileFilter: (_req, file, callback) => {
        if (!ALLOWED_MIME_TYPES.includes(file.mimetype)) {
          callback(
            new BadRequestException(`不支持的文件类型：${file.mimetype}`),
            false,
          );
          return;
        }
        callback(null, true);
      },
    }),
  )
  async upload(
    @Req() req: Request,
    @UploadedFile() file: Express.Multer.File,
  ) {
    const userId = (req.user as any).userId;
    const filename = req.body?.filename || file?.originalname;
    return this.documentService.upload(userId, file, filename);
  }

  @Post(':id/process')
  @HttpCode(HttpStatus.ACCEPTED)
  async process(@Req() req: Request, @Param('id') id: string) {
    const userId = (req.user as any).userId;
    await this.documentService.findById(id, userId);

    void this.chunkService.processDocument(id, userId).catch((error) => {
      console.error(`[DocumentProcess] documentId=${id} failed:`, error);
    });

    return { message: '处理已开始', documentId: id };
  }

  @Get()
  async findAll(@Req() req: Request) {
    const userId = (req.user as any).userId;
    return this.documentService.findByUser(userId);
  }

  @Get(':id')
  async findOne(@Req() req: Request, @Param('id') id: string) {
    const userId = (req.user as any).userId;
    return this.documentService.findById(id, userId);
  }

  @Delete(':id')
  @HttpCode(HttpStatus.NO_CONTENT)
  async remove(@Req() req: Request, @Param('id') id: string) {
    const userId = (req.user as any).userId;
    await this.documentService.delete(id, userId);
  }
}
