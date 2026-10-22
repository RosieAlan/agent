# D04第八块：统一超时配置与理解整次调用期限

2026-10-22。原1.5.6异常处理、1.6.7重试及第二章环境配置承接；原手写循环为教学原理，当前实现继续使用已安装模型适配器的maxRetries。新增代码仅迁移配置常量，两处创建取消信号保持各任务独立。

学生上一块5文件已实际写入，教师实际运行bun x tsc --noEmit --incremental false，退出码0。浏览器跨入口并发行为待交，复用其既有取消证据。

必备：maxRetries限制额外尝试次数，signal限定本次处理的取消期限；一个任务的多次尝试共用该任务signal；两个任务共用超时毫秒数，各自创建signal。熟悉：模块级配置加载与校验。了解：取消信号触发、SDK异常返回、供应商停止计算分别观察。

时间例：0秒第一次调用，8秒收到可重试错误，等待2秒，10秒第二次调用，30秒本任务取消信号触发。创建计时器在重试循环外，所以沿用0秒开始的计时；若每轮重建30秒信号，会扩张整次等待。maxRetries=2允许最多3次尝试，实际可能因成功、不可重试错误、取消或超时提前结束。当前结构化maxRetries2，流式maxRetries0；共享总期限概念不要求两者重试次数相同。

既有本地HTTP测试显示退避等待期间取消会阻止第二次HTTP，但返回异常可能延迟；本块仅统一配置，及时退出退避等待将在D04最后边界专题处理。AbortSignal.timeout提供触发时间，事件循环调度及SDK处理影响异常返回时机，避免声称严格墙钟上限。计时范围目前从应用接收后创建signal开始，另需考虑代理/队列/网络的外部期限。

变更：新建model-call.config.ts；RequirementService移出zod及原配置定义，导入共享常量；Controller导入同常量并替换stream的30000。Module无需注册普通导出常量。config在load-env之后加载，编辑services/chat/.env后完整重启。

## model-call.config.ts

```ts
import { z } from 'zod';

// 两条入口共用同一份配置；环境加载后，在模块加载时转换并校验。
export const MODEL_TIMEOUT_MS = z.coerce.number()
  .int() // 必须为整数毫秒
  .min(1)
  .max(120_000)
  .default(30_000) // 未配置时为30秒
  .parse(process.env.REQUIREMENT_TIMEOUT_MS);
```

## requirement.service.ts

```ts
import {
  GatewayTimeoutException,
  Injectable,
  Logger,
} from '@nestjs/common';
import { randomUUID } from 'node:crypto';
import {
  RequirementResultSchema,
  type RequirementResult,
} from '@autix/contracts';
import { createChatModel } from './model.factory.js';
import { requirementPrompt } from './requirement.prompt-builder.js';
import { ModelAdmissionService } from './model-admission.service.js';
import { MODEL_TIMEOUT_MS } from './model-call.config.js';

@Injectable()
export class RequirementService {
  private readonly logger = new Logger(RequirementService.name);
  private model = createChatModel({ maxRetries: 2 });

  // 新增：Nest传入共用的计数Service。
  constructor(private readonly admission: ModelAdmissionService) {}

  async extract(
    input: string,
    clientSignal?: AbortSignal,
  ): Promise<RequirementResult> {
    clientSignal?.throwIfAborted(); // 已取消的请求直接结束

    // 新增：通过共享检查后，取得本次任务的归还函数。
    const release = this.admission.enter();

    const requestId = randomUUID();
    const startedAt = performance.now();
    let outcome = 'failed';

    const timeoutSignal = AbortSignal.timeout(MODEL_TIMEOUT_MS);
    const signal = clientSignal
      ? AbortSignal.any([clientSignal, timeoutSignal])
      : timeoutSignal;

    try {
      const messages = await requirementPrompt.formatMessages({ input });
      signal.throwIfAborted();

      const structuredModel = this.model.withStructuredOutput(
        RequirementResultSchema,
      );

      const result = await structuredModel.invoke(messages, { signal });
      signal.throwIfAborted();

      outcome = 'success';
      return result;
    } catch (error) {
      if (
        timeoutSignal.aborted &&
        signal.reason === timeoutSignal.reason
      ) {
        outcome = 'timeout';
        throw new GatewayTimeoutException('模型响应超时，请稍后再试');
      }

      if (
        clientSignal?.aborted &&
        signal.reason === clientSignal.reason
      ) {
        outcome = 'cancelled';
      }

      throw error; // 原错误继续交给调用方处理
    } finally {
      release(); // 修改：归还共享名额

      const entry = JSON.stringify({
        event: 'requirement.extract.finished',
        requestId,
        outcome,
        durationMs: Math.round(performance.now() - startedAt),
      });

      if (outcome === 'failed' || outcome === 'timeout') {
        this.logger.error(entry);
      } else {
        this.logger.log(entry);
      }
    }
  }
}
```

## llm.controller.ts

```ts
import { Body, Controller, Post, Res ,BadRequestException} from '@nestjs/common';
import type { Response } from 'express';
import { LlmService } from './llm.service.js';
import { RequirementService } from './requirement.service.js';
import { RequirementSchema } from '@autix/contracts';
import { ModelAdmissionService } from './model-admission.service.js';
import { MODEL_TIMEOUT_MS } from './model-call.config.js';
@Controller('api/langchain')
export class LlmController {
constructor(
  private readonly llmService: LlmService,
  private readonly requirementService: RequirementService,
  private readonly admission: ModelAdmissionService, // 新增共用计数
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

  // 新增：发送SSE响应头前检查；超额时抛出HTTP429。
  const release = this.admission.enter();

  const client = new AbortController();
  const timeout = AbortSignal.timeout(MODEL_TIMEOUT_MS);
  const signal = AbortSignal.any([client.signal, timeout]);

  const onClose = () => {
    if (!res.writableEnded) client.abort(); // 连接断开时取消模型调用
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

    const stream = await this.llmService.streamDemo(
      checked.data.input,
      signal,
    );

    // 在整个读取期间持续占用名额。
    for await (const chunk of stream) {
      signal.throwIfAborted();
      if (chunk.text) {
        send({ type: 'delta', text: chunk.text });
      }
    }

    signal.throwIfAborted();
    send({ type: 'done' });
  } catch {
    if (!client.signal.aborted) {
      const timedOut =
        timeout.aborted && signal.reason === timeout.reason;

      send({
        type: 'error',
        message: timedOut
          ? '生成超时，请重新提交'
          : '生成失败，请重新提交',
      });
    }
  } finally {
    release(); // 新增：流结束、失败或取消后，归还共享名额
    res.off('close', onClose);

    if (!res.destroyed && !res.writableEnded) {
      res.end();
    }
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
```

## 必背与综合题答案

超时配置共享的是允许等待的时长，每次请求都创建自己的取消信号。重试次数限制额外尝试，整次任务期限限制总等待，两者共同生效。取消信号用于通知本地调用停止，供应商是否已经停止计算及计费需看其实现和状态。

问：并行任务A启动10秒后B启动，共享30000常量，何时触发？答：A启动约30秒后，B启动约30秒后，各自计算。问：第一次失败耗时20秒，再等待2秒，第二次还剩多少计划等待时间？答：总期限30秒时约8秒，具体返回时机仍取决于SDK如何响应取消。问：流式已发HTTP200后超时？答：发送error事件、结束流，页面按错误处理并保留已收到的部分文字；普通接口通过GatewayTimeoutException返回504。

学生动作：创建配置文件并修改两处引用；运行后端类型检查；需要浏览器验证时将REQUIREMENT_TIMEOUT_MS临时设为1000并重启，两按钮在调用超过该期限时分别显示普通超时与流式error，完成后恢复30000并重启。已有快响应不视为超时失败证据。学生独立解释常量共享与signal独立。

教师验证：候选完整后端类型检查及12项配置/实际共享计数断言通过，供应商请求0次。学生本块修改及页面验收待交。
