import { GatewayTimeoutException, Injectable } from '@nestjs/common';
import {
  RequirementResultSchema,
  type RequirementResult,
} from '@autix/contracts';
import { createChatModel } from './model.factory.js';
import { requirementPrompt } from './requirement.prompt-builder.js';

const MODEL_TIMEOUT_MS = 30_000;

@Injectable()
export class RequirementService {
  private model = createChatModel();

  async extract(
    input: string,
    clientSignal?: AbortSignal,
  ): Promise<RequirementResult> {
    const messages = await requirementPrompt.formatMessages({ input });
    const structuredModel = this.model.withStructuredOutput(
      RequirementResultSchema,
    );
    const timeoutSignal = AbortSignal.timeout(MODEL_TIMEOUT_MS);
    const signal = clientSignal
      ? AbortSignal.any([clientSignal, timeoutSignal])
      : timeoutSignal;

    try {
      return await structuredModel.invoke(messages, { signal });
    } catch (error) {
      if (timeoutSignal.aborted && signal.reason === timeoutSignal.reason) {
        throw new GatewayTimeoutException('模型响应超过30秒，请稍后再试');
      }
      throw error;
    }
  }
}