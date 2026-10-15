import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { load } from 'js-yaml';

export type LangChainAppConfig = {
  llm: {
    provider: string;
    model: string;
    temperature: number;
    maxTokens: number;
  };
  retrieval: {
    enabled: boolean;
    topK: number;
  };
  tools: {
    enableConstraintCheck: boolean;
    enableEntityLookup: boolean;
  };
  features: {
    enableStructuredOutput: boolean;
    enableStreaming: boolean;
  };
};

export function loadLangChainConfig(): LangChainAppConfig {
  const filePath = join(
    process.cwd(),
    'config',
    'langchain.yaml',
  );
  const raw = readFileSync(filePath, 'utf8');
  return load(raw) as LangChainAppConfig;
}

export function getApiKeys() {
  return {
    openaiApiKey: process.env.OPENAI_API_KEY ?? '',
    openaiBaseUrl: process.env.OPENAI_BASE_URL,
  };
}
