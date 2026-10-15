import { Test, TestingModule } from '@nestjs/testing';
import { AppController } from './app.controller.js';
import { AppService } from './app.service.js';
import { RequirementService } from './llm/requirement.service.js';

describe('AppController', () => {
  let appController: AppController;

  beforeEach(async () => {
    const app: TestingModule = await Test.createTestingModule({
      controllers: [AppController],
      providers: [
        AppService,
        {
          provide: RequirementService,
          useValue: { extract: vi.fn() },
        },
      ],
    }).compile();

    appController = app.get<AppController>(AppController);
  });

  it('health 返回 ok', () => {
    expect(appController.getHealth()).toEqual({ ok: true });
  });

  it('hello 返回共享包里的 APP_NAME', () => {
    expect(appController.getHello()).toEqual({
      message: 'Hello from Chat, APP_NAME=llm',
    });
  });
});
