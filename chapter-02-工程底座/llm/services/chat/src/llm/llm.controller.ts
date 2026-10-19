import { Body, Controller, Post, Res ,BadRequestException} from '@nestjs/common';
import type { Response } from 'express';
import { LlmService } from './llm.service.js';
import { RequirementService } from './requirement.service.js';
import { RequirementSchema } from '@autix/contracts';
@Controller('api/langchain')
export class LlmController {
  constructor(
    private readonly llmService: LlmService,
    private readonly requirementService: RequirementService,
  ) {}

  @Post('invoke')
  async invoke(@Body() body: { input: string }) {
    const result = await this.llmService.invokeDemo(body.input);
    return { result };
  }

  @Post('stream')
  async stream(
    @Body() body: { input: string },
    @Res() res: Response,
  ) {
    res.setHeader(
      'Content-Type',
      'text/event-stream; charset=utf-8',
    );
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');

    const stream = await this.llmService.streamDemo(body.input);
    for await (const chunk of stream) {
      res.write(chunk.text);
    }
    res.end();
  }

  @Post('batch')
  async batch(@Body() body: { inputs: string[] }) {
    const results = await this.llmService.batchDemo(body.inputs);
    return { results };
  }

  @Post('prompt-preview')
  async promptPreview(@Body() body: { input: string }) {
    return this.llmService.promptPreview(body.input);
  }

  @Post('prompt-to-model')
  async promptToModel(@Body() body: { input: string }) {
    return this.llmService.promptToModel(body.input);
  }

  @Post('chain-invoke')
  async chainInvoke(@Body() body: { input: string }) {
    return this.llmService.chainInvoke(body.input);
  }

  @Post('chain-stream')
  async chainStream(
    @Body() body: { input: string },
    @Res() res: Response,
  ) {
    res.setHeader(
      'Content-Type',
      'text/event-stream; charset=utf-8',
    );
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');

    const stream = await this.llmService.chainStream(body.input);
    for await (const chunk of stream) {
      res.write(chunk);
    }
    res.end();
  }

  @Post('chain-batch')
  async chainBatch(@Body() body: { inputs: string[] }) {
    return this.llmService.chainBatch(body.inputs);
  }

  // @Post('structured')
  // async structured(@Body() body: { input: string }) {
  //   return this.requirementService.extract(body.input);
  // }
  @Post('structured')
  async structured(@Body() body: unknown) {
    const checked = RequirementSchema.safeParse(body);

    if (!checked.success) {
      throw new BadRequestException('input必须是非空字符串');
    }

    return this.requirementService.extract(checked.data.input);
  }
  @Post('tool-bind')
  async toolBind(@Body() body: { input: string }) {
    return this.llmService.toolBindDemo(body.input);
  }

  @Post('tool-loop')
  async toolLoop(@Body() body: { input: string }) {
    return this.llmService.toolLoopDemo(body.input);
  }
}
