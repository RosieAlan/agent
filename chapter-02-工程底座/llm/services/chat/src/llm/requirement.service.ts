import {
  GatewayTimeoutException,
  HttpException,
  HttpStatus,
  Injectable,
} from '@nestjs/common';
import {
  RequirementResultSchema,
  type RequirementResult,
} from '@autix/contracts';
import { createChatModel } from './model.factory.js';
import { requirementPrompt } from './requirement.prompt-builder.js';

const MODEL_TIMEOUT_MS = 30_000;
const RATE_WINDOW_MS = 10_000;
const MAX_REQUESTS_PER_WINDOW = 5;
const MAX_CONCURRENT = 2;

@Injectable()
export class RequirementService {
  private model = createChatModel({ maxRetries: 2 });
  private activeRequests = 0;
  private windowStartedAt = Date.now();
  private windowRequestCount = 0;

  async extract(
    input: string,
    clientSignal?: AbortSignal,
  ): Promise<RequirementResult> {
    clientSignal?.throwIfAborted();

    const now = Date.now();
    if (now - this.windowStartedAt >= RATE_WINDOW_MS) {
      this.windowStartedAt = now;
      this.windowRequestCount = 0;
    }
    if (this.windowRequestCount >= MAX_REQUESTS_PER_WINDOW) {
      throw new HttpException('请求过于频繁，请稍后再试', HttpStatus.TOO_MANY_REQUESTS);
    }
    if (this.activeRequests >= MAX_CONCURRENT) {
      throw new HttpException('当前分析任务较多，请稍后再试', HttpStatus.TOO_MANY_REQUESTS);
    }

    this.windowRequestCount++;
    this.activeRequests++;

    const timeoutSignal = AbortSignal.timeout(MODEL_TIMEOUT_MS);
    const signal = clientSignal
      ? AbortSignal.any([clientSignal, timeoutSignal])
      : timeoutSignal;

    try {
      const messages = await requirementPrompt.formatMessages({ input });
      signal.throwIfAborted();
      const structuredModel = this.model.withStructuredOutput(RequirementResultSchema);
      return await structuredModel.invoke(messages, { signal });
    } catch (error) {
      if (timeoutSignal.aborted && signal.reason === timeoutSignal.reason) {
        throw new GatewayTimeoutException('模型响应超过30秒，请稍后再试');
      }
      throw error;
    } finally {
      this.activeRequests--;
    }
  }
}