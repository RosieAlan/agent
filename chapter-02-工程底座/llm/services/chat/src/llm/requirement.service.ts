import {
  GatewayTimeoutException,
  Injectable,
} from '@nestjs/common';
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

  async extract(input: string): Promise<RequirementResult> {
    const messages = await requirementPrompt.formatMessages({
      input,
    });

    const structuredModel = this.model.withStructuredOutput(
      RequirementResultSchema,
    );

    const signal = AbortSignal.timeout(MODEL_TIMEOUT_MS);

    try {
      return await structuredModel.invoke(messages, { signal });
    } catch (error) {
      if (signal.aborted) {
        throw new GatewayTimeoutException(
          '模型响应超过30秒，请稍后再试',
        );
      }

      throw error;
    }
  }
}