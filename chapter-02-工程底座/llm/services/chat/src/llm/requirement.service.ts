import { Injectable } from '@nestjs/common';
import {
  RequirementResultSchema,
  type RequirementResult,
} from '@autix/contracts';
import { createChatModel } from './model.factory.js';
import { requirementPrompt } from './requirement.prompt-builder.js';

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
    return structuredModel.invoke(messages);
  }
}
