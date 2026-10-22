# D04第七块：普通提交与流式分析共用任务计数

2026-10-22。原第二章Service/依赖注入封装与原6.5.4流式生命周期承接；岗位并发控制补充。本轮使用using-superpowers、karpathy-guidelines及完成前验证。核对Nest官方providers默认单例与构造器注入：https://docs.nestjs.com/providers 。

学生提交真实取消日志：2026/10/22 11:09:15，requestId fc4f24cb-8993-400a-9549-cb593a4e32be，outcome cancelled，durationMs 17542。证据确认后端断开监听和Service取消结束日志；durationMs为整次调用耗时，取消后响应延迟尚待测量。

必备：两条入口复用同一实例的计数；enter成功占用且返回release，finally归还；SSE在flushHeaders之前检查，以便拒绝时返回HTTP429。熟悉：函数返回函数与闭包、Nest默认单例；了解：单进程全局窗口，多进程需共享存储与原子计数。

改动：新增ModelAdmissionService；Module注册一次；RequirementService迁出原计数并注入；Controller仅给stream入口增加检查和finally释放，structured入口继续由RequirementService检查。旧演示invoke/batch等路由仍为历史练习，本轮只覆盖/d03两个按钮。入场函数无await，检查和增量在当前JS线程同步完成。归还并发名额保留窗口已接收次数。流式名额从开始处理保持到整个迭代结束。

以下完整文件为教学候选代码，教师保存在讲义用于类型和固定数据校验；业务文件由学生按对话修改。流式30秒配置仍独立，跨接口统一超时留下一块明确收尾。

## model-admission.service.ts

```ts
import { HttpException, HttpStatus, Injectable } from '@nestjs/common';

const RATE_WINDOW_MS = 10_000; // 一个计数窗口为10秒
const MAX_REQUESTS_PER_WINDOW = 5; // 每个窗口最多接收5个任务
const MAX_CONCURRENT = 2; // 最多同时处理2个任务

@Injectable()
export class ModelAdmissionService {
  private activeRequests = 0; // 已接收且尚未结束的任务数
  private windowStartedAt = Date.now(); // 当前窗口的开始时间
  private windowRequestCount = 0; // 当前窗口已接收的任务数

  enter(): () => void { // 返回一个函数，供调用方结束时归还名额
    const now = Date.now();
    if (now - this.windowStartedAt >= RATE_WINDOW_MS) {
      this.windowStartedAt = now;
      this.windowRequestCount = 0; // 新窗口重新计算接收次数
    }
    if (this.windowRequestCount >= MAX_REQUESTS_PER_WINDOW) {
      throw new HttpException('请求过于频繁，请稍后再试', HttpStatus.TOO_MANY_REQUESTS);
    }
    if (this.activeRequests >= MAX_CONCURRENT) {
      throw new HttpException('当前分析任务较多，请稍后再试', HttpStatus.TOO_MANY_REQUESTS);
    }
    this.windowRequestCount++;
    this.activeRequests++; // 检查与加计数之间保持同步执行

    let released = false; // 每次enter都有自己的一份归还标记
    return () => {
      if (released) return; // 重复调用时只归还一次
      released = true;
      this.activeRequests--;
    };
  }
}
```

## requirement.service.ts

```ts
import {
  GatewayTimeoutException,
  Injectable,
  Logger, // Nest自带的日志工具
} from '@nestjs/common';
import { randomUUID } from 'node:crypto'; // 为本次分析生成日志编号
import { z } from 'zod'; // 校验配置值
import {
  RequirementResultSchema,
  type RequirementResult,
} from '@autix/contracts';
import { createChatModel } from './model.factory.js';
import { requirementPrompt } from './requirement.prompt-builder.js';
import { ModelAdmissionService } from './model-admission.service.js';

// 环境变量是字符串：先转换成数字，再检查范围。
// 未配置时默认30000毫秒；配置错误时，在启动阶段报错。
const MODEL_TIMEOUT_MS = z.coerce.number()
  .int()                 // 必须是整数
  .min(1)                // 最少1毫秒
  .max(120_000)          // 本练习最多120秒
  .default(30_000)       // 未配置时使用30秒
  .parse(process.env.REQUIREMENT_TIMEOUT_MS);

@Injectable()
export class RequirementService {
  // 日志来源显示为RequirementService。
  private readonly logger = new Logger(RequirementService.name);

  private model = createChatModel({ maxRetries: 2 });
  constructor(private readonly admission: ModelAdmissionService) {}

  async extract(
    input: string,
    clientSignal?: AbortSignal,
  ): Promise<RequirementResult> {
    // 已经取消的请求直接结束。
    clientSignal?.throwIfAborted();

    const release = this.admission.enter(); // 检查共享名额，接收成功后取得归还函数

    // 通过入口检查后，为本次分析准备日志信息。
    const requestId = randomUUID();
    const startedAt = performance.now();
    let outcome = 'failed'; // 后续根据实际结果修改

    const timeoutSignal = AbortSignal.timeout(MODEL_TIMEOUT_MS);

    // 用户取消或者到达超时时间，都可以取消模型调用。
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

      // 返回结果前，再检查一次取消或超时。
      signal.throwIfAborted();

      outcome = 'success';
      return result;
    } catch (error) {
      // 根据首次触发的取消原因，判断是否为超时。
      if (
        timeoutSignal.aborted &&
        signal.reason === timeoutSignal.reason
      ) {
        outcome = 'timeout';
        throw new GatewayTimeoutException('模型响应超时，请稍后再试');
      }

      // 用户取消单独记录，便于与调用失败区分。
      if (
        clientSignal?.aborted &&
        signal.reason === clientSignal.reason
      ) {
        outcome = 'cancelled';
      }

      // 原错误继续交给Controller/Nest处理。
      throw error;
    } finally {
      // 成功、失败、取消、超时，都释放并发名额。
      release(); // 归还共享名额

      // 仅把明确允许的字段放进日志。
      const entry = JSON.stringify({
        event: 'requirement.extract.finished',
        requestId,
        outcome,
        durationMs: Math.round(performance.now() - startedAt),
      });

      if (outcome === 'failed' || outcome === 'timeout') {
        this.logger.error(entry); // 操作失败或超时，记录错误级别
      } else {
        this.logger.log(entry); // 成功和用户主动取消
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
@Controller('api/langchain')
export class LlmController {
  constructor(
    private readonly llmService: LlmService,
    private readonly requirementService: RequirementService,
    private readonly admission: ModelAdmissionService,
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

  const release = this.admission.enter(); // 发送SSE响应头前检查，超额由Nest返回HTTP429
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
    release(); // 整个流结束、失败或取消时，归还名额
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
```

## llm.module.ts

```ts
import { Module } from '@nestjs/common';
import { LlmController } from './llm.controller.js';
import { LlmService } from './llm.service.js';
import { RequirementService } from './requirement.service.js';
import { ModelAdmissionService } from './model-admission.service.js';

@Module({
  providers: [LlmService, RequirementService, ModelAdmissionService],
  controllers: [LlmController],
  exports: [LlmService, RequirementService],
})
export class LlmModule {}
```

## 必背与验收

必背：同一个Nest模块注册的默认单例Service由依赖方复用，两条入口调用同一实例即可共享计数。每次任务接收成功得到归还函数，在finally调用；频率计数在窗口到期时重置，并发计数在任务结束时减少。SSE发送响应头之前完成拒绝判断，接收后异常通过error事件表达。

浏览器：在3002/d03的三个标签页准备请求，两个任务保持处理中时第三次提交应被429拒绝；取消一个并等待服务端处理结束，同窗口剩余频率额度允许时新任务可接收。窗口内已接收5个后第6个即使并发为0仍拒绝。真实模型速度影响手工并发复现，固定数据验证补足确定性证据。

综合题及答案：一个普通+一个流式处理中，再来一个流式→429；取消一个后归还的是并发名额，窗口次数保留；每条路由各自new实例会维护两份计数，采用同一模块注册的默认实例共享。多进程总限制需要统一存储及原子更新。

## requirement.spec.ts

已有集成测试同步传入新增依赖；保留RUN_LLM_E2E默认跳过行为。

```ts
import '../src/load-env.js';
import { RequirementService } from '../src/llm/requirement.service.js';
import { ModelAdmissionService } from '../src/llm/model-admission.service.js';

const runIf = process.env.RUN_LLM_E2E ? it : it.skip;

describe('RequirementService.extract', () => {
  runIf(
    '按约定结构返回抽取结果',
    async () => {
      const service = new RequirementService(new ModelAdmissionService());
      const result = await service.extract(
        '用户注册时必须绑定手机号，密码至少8位',
      );

      expect(typeof result.action).toBe('string');
      expect(result.action.length).toBeGreaterThan(0);
      expect(Array.isArray(result.constraints)).toBe(true);
      expect(result.constraints.length).toBeGreaterThan(0);
      expect(Array.isArray(result.entities)).toBe(true);
      expect(JSON.stringify(result)).toContain('手机号');
    },
    60000,
  );
});
```

教师验证：拟议5文件完整后端类型检查通过；固定数据/接入结构14项断言通过，供应商请求0次。学生修改与浏览器验收待交。
