import {
  Body,
  Controller,
  Post,
  Req,
  UseGuards,
  UsePipes,
  ValidationPipe,
} from '@nestjs/common';
import { Transform } from 'class-transformer';
import {
  IsInt,
  IsNotEmpty,
  IsOptional,
  IsString,
  Max,
  MaxLength,
  Min,
} from 'class-validator';
import type { Request } from 'express';
import { JwtAuthGuard } from '../auth/jwt-auth.guard.js';
import { SearchService } from './search.service.js';

class SearchDto {
  @IsString()
  @IsNotEmpty()
  @MaxLength(1000)
  query!: string;

  @IsOptional()
  @Transform(({ value }) => Number(value))
  @IsInt()
  @Min(1)
  @Max(20)
  topK = 5;
}

@UseGuards(JwtAuthGuard)
@Controller('api/search')
export class SearchController {
  constructor(private readonly searchService: SearchService) {}

  @Post()
  @UsePipes(new ValidationPipe({ transform: true, whitelist: true }))
  async search(@Req() req: Request, @Body() body: SearchDto) {
    const userId = (req.user as any).userId;
    return this.searchService.similaritySearch(
      body.query,
      userId,
      body.topK,
    );
  }
}
