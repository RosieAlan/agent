import {
  GatewayTimeoutException,
  Injectable,
  Logger,
} from '@nestjs/common';
import { randomUUID } from 'node:crypto';
import { z } from 'zod';
import {
  RequirementResultSchema,
  type RequirementResult,
} from '@autix/contracts';
import { createChatModel } from './model.factory.js';
import { requirementPrompt } from './requirement.prompt-builder.js';
import { ModelAdmissionService } from './model-admission.service.js';

// 沿用上一块：读取并校验超时配置。
const MODEL_TIMEOUT_MS = z.coerce.number()
  .int()
  .min(1)
  .max(120_000)
  .default(30_000)
  .parse(process.env.REQUIREMENT_TIMEOUT_MS);

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