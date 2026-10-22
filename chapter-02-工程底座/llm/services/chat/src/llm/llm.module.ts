import { Module } from '@nestjs/common';
import { LlmController } from './llm.controller.js';
import { LlmService } from './llm.service.js';
import { RequirementService } from './requirement.service.js';
import { ModelAdmissionService } from './model-admission.service.js';

@Module({
  providers: [
    LlmService,
    RequirementService,
    ModelAdmissionService, // 新增：交给Nest创建和管理
  ],
  controllers: [LlmController],
  exports: [LlmService, RequirementService],
})
export class LlmModule {}