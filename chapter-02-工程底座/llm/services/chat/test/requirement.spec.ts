import '../src/load-env.js';
import { RequirementService } from '../src/llm/requirement.service.js';
import { ModelAdmissionService } from '../src/llm/model-admission.service.js';
const runIf = process.env.RUN_LLM_E2E ? it : it.skip;

describe('RequirementService.extract', () => {
  runIf(
    '按约定结构返回抽取结果',
    async () => {
      const service = new RequirementService(
        new ModelAdmissionService(), // 测试手动创建对象，因此手动提供依赖
      );
      const result = await service.extract(
        '用户注册时必须绑定手机号，密码至少8位',
      );

      expect(typeof result.action).toBe('string');
      expect(result.action.length).toBeGreaterThan(0);
      expect(Array.isArray(result.constraints)).toBe(true);
      expect(result.constraints.length).toBeGreaterThan(0);
      expect(Array.isArray(result.entities)).toBe(true);
      expect(JSON.stringify(result)).toContain('手机号');
    },
    60000,
  );
});
