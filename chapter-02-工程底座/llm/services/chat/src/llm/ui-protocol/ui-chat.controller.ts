import {
  Body,
  Controller,
  Post,
} from '@nestjs/common';
import {
  UIFlowService,
} from './ui-flow.service.js';
import {
  UIResponseService,
} from './ui-response.service.js';
import type {
  UIAction,
} from './ui-types.js';

@Controller('api/ui-chat')
export class UIChatController {
  constructor(
    private readonly uiFlow:
      UIFlowService,
    private readonly uiResponse:
      UIResponseService,
  ) {}

  @Post('chat')
  chat(
    @Body()
    body: {
      sessionId: string;
      input: string;
    },
  ) {
    return this.uiFlow.handleInput(
      body.sessionId,
      body.input,
    );
  }

  @Post('action')
  action(
    @Body()
    body: {
      sessionId: string;
      action: UIAction;
    },
  ) {
    return this.uiFlow.handleAction(
      body.sessionId,
      body.action,
    );
  }

  @Post('generate')
  generate(
    @Body()
    body: {
      input: string;
      context?: Record<
        string,
        unknown
      >;
    },
  ) {
    return this.uiResponse
      .generateUIResponse(
        body.input,
        [],
        body.context,
      );
  }
}
