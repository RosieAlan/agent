import { z } from 'zod';
import { RequirementSchema } from './schema.js';

const mode = process.argv[2] ?? 'success';

async function getDemoResponse(): Promise<string> {
  if (mode === 'upstream') {
    throw Object.assign(new Error('模拟上游限流'), {
      status: 429,
    });
  }

  if (mode === 'json') {
    return '{"features": [';
  }

 return JSON.stringify({
  features: ['导入 Excel'],
  constraints: mode === 'schema' ? 10000 : ['最多一万行'],
  missingInformation: ['一万行的适用范围待确认'],
});
}

async function main() {
  let stage: 'request' | 'parse' | 'validate' = 'request';

  try {
    const text = await getDemoResponse();

    stage = 'parse';
    const data: unknown = JSON.parse(text);

    stage = 'validate';
    const result = RequirementSchema.parse(data);

    console.log('成功：', result);
  } catch (error: unknown) {
    console.error('失败阶段：', stage);
    console.error(
      '错误类型：',
      error instanceof Error ? error.name : '未知错误',
    );

    if (error instanceof z.ZodError) {
      console.error('字段问题：', error.issues);
    }

    if (
      typeof error === 'object' &&
      error !== null &&
      'status' in error
    ) {
      console.error('状态码：', error.status);
    }

    process.exitCode = 1;
  }
}

void main();