import {
  GatewayTimeoutException,
  HttpException,
  HttpStatus,
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

// 环境变量是字符串：先转换成数字，再检查范围。
// 未配置时默认30000毫秒；配置错误时，在启动阶段报错。
const MODEL_TIMEOUT_MS = z.coerce.number()
  .int()                 // 必须是整数
  .min(1)                // 最少1毫秒
  .max(120_000)          // 本练习最多120秒
  .default(30_000)       // 未配置时使用30秒
  .parse(process.env.REQUIREMENT_TIMEOUT_MS);

const RATE_WINDOW_MS = 10_000;
const MAX_REQUESTS_PER_WINDOW = 5;
const MAX_CONCURRENT = 2;

@Injectable()
export class RequirementService {
  // 日志来源显示为RequirementService。
  private readonly logger = new Logger(RequirementService.name);

  private model = createChatModel({ maxRetries: 2 });
  private activeRequests = 0;
  private windowStartedAt = Date.now();
  private windowRequestCount = 0;

  async extract(
    input: string,
    clientSignal?: AbortSignal,
  ): Promise<RequirementResult> {
    // 已经取消的请求直接结束。
    clientSignal?.throwIfAborted();

    // 以下沿用上一块的频率和并发检查。
    const now = Date.now();

    if (now - this.windowStartedAt >= RATE_WINDOW_MS) {
      this.windowStartedAt = now;
      this.windowRequestCount = 0;
    }

    if (this.windowRequestCount >= MAX_REQUESTS_PER_WINDOW) {
      throw new HttpException(
        '请求过于频繁，请稍后再试',
        HttpStatus.TOO_MANY_REQUESTS,
      );
    }

    if (this.activeRequests >= MAX_CONCURRENT) {
      throw new HttpException(
        '当前分析任务较多，请稍后再试',
        HttpStatus.TOO_MANY_REQUESTS,
      );
    }

    this.windowRequestCount++;
    this.activeRequests++;

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
      this.activeRequests--;

      // 仅把明确允许的字段放进日志。
      const entry = JSON.stringify({
        event: 'requirement.extract.finished',
        requestId,
        outcome,
        durationMs: Math.round(performance.now() - startedAt),
      });

      if (outcome === 'failed' || outcome === 'timeout') {
        this.logger.warn(entry); // 失败和超时，便于按警告级别筛选
      } else {
        this.logger.log(entry); // 成功和用户主动取消
      }
    }
  }
}