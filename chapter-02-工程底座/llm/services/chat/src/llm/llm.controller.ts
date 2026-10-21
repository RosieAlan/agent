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
async stream(@Body() body: unknown, @Res() res: Response) {
  const checked = RequirementSchema.safeParse(body);
  if (!checked.success) {
    throw new BadRequestException('input必须是非空字符串');
  }

  const client = new AbortController();
  const timeout = AbortSignal.timeout(30_000);
  const signal = AbortSignal.any([client.signal, timeout]);
  const onClose = () => {
    if (!res.writableEnded) client.abort();
  };
  const send = (event: object) => {
    if (!res.destroyed && !res.writableEnded) {
      res.write(`data: ${JSON.stringify(event)}\n\n`);
    }
  };
  res.on('close', onClose);

  try {
    res.status(200);
    res.setHeader('Content-Type', 'text/event-stream; charset=utf-8');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('X-Accel-Buffering', 'no');
    res.flushHeaders();
    send({ type: 'start' });

    const stream = await this.llmService.streamDemo(checked.data.input, signal);
    for await (const chunk of stream) {
      signal.throwIfAborted();
      if (chunk.text) send({ type: 'delta', text: chunk.text });
    }
    signal.throwIfAborted();
    send({ type: 'done' });
  } catch {
    if (!client.signal.aborted) {
      const timedOut = timeout.aborted && signal.reason === timeout.reason;
      send({
        type: 'error',
        message: timedOut ? '生成超时，请重新提交' : '生成失败，请重新提交',
      });
    }
  } finally {
    res.off('close', onClose);
    if (!res.destroyed && !res.writableEnded) res.end();
  }
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
  async structured(
    @Body() body: unknown,
    @Res({ passthrough: true }) res: Response,
  ) {
    const checked = RequirementSchema.safeParse(body);
    if (!checked.success) {
      throw new BadRequestException('input必须是非空字符串');
    }

    const controller = new AbortController();
    const onClose = () => {
      if (!res.writableEnded) {
        controller.abort(new Error('客户端已断开连接'));
        console.info('[structured] 客户端断开，已向模型调用发送取消信号');
      }
    };
    res.on('close', onClose);

    try {
      return await this.requirementService.extract(
        checked.data.input,
        controller.signal,
      );
    } catch (error) {
      if (controller.signal.aborted) return;
      throw error;
    } finally {
      res.off('close', onClose);
    }
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
