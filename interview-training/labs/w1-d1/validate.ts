import { RequirementSchema } from './schema.js';

const validData = {
  features: ['导入 Excel'],
  constraints: ['最多一万行'],
  missingInformation: ['一万行的适用范围待确认'],
};

const invalidData = {
  features: 123,
  constraints: '最多一万行',
  missingInformation: [],
};

for (const [name, data] of [
  ['合法数据', validData],
  ['非法数据', invalidData],
] as const) {
  const result = RequirementSchema.safeParse(data);

  console.log(name, '校验通过：', result.success);

  if (!result.success) {
    console.log(result.error.issues);
  }
}