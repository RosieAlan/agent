import { StringOutputParser } from '@langchain/core/output_parsers';
import { createChatModel } from './model.factory.js';
import { requirementPrompt } from './requirement.prompt-builder.js';

const model = createChatModel();
const parser = new StringOutputParser();

export const requirementChain = requirementPrompt
  .pipe(model)
  .pipe(parser);
