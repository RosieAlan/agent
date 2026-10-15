import { ChatOpenAI } from '@langchain/openai';
import { ProxyAgent } from 'undici';
import {
  getApiKeys,
  loadLangChainConfig,
} from '../config/load-langchain-config.js';

class ChatCompletionsOpenAI extends ChatOpenAI {
  protected override _useResponsesApi(): boolean {
    return false;
  }

  override withConfig(
    config: Parameters<ChatOpenAI['withConfig']>[0],
  ): ReturnType<ChatOpenAI['withConfig']> {
    const model = new ChatCompletionsOpenAI(this.fields);
    model.defaultOptions = {
      ...this.defaultOptions,
      ...config,
    };
    return model;
  }
}

export function createChatModel() {
  const config = loadLangChainConfig();
  const keys = getApiKeys();
  const proxyUrl = process.env.HTTPS_PROXY ?? process.env.HTTP_PROXY;

  return new ChatCompletionsOpenAI({
    model: config.llm.model,
    temperature: config.llm.temperature,
    maxTokens: config.llm.maxTokens,
    apiKey: keys.openaiApiKey,
    configuration: {
      ...(keys.openaiBaseUrl ? { baseURL: keys.openaiBaseUrl } : {}),
      ...(proxyUrl
        ? { fetchOptions: { dispatcher: new ProxyAgent(proxyUrl) } }
        : {}),
    },
  });
}
