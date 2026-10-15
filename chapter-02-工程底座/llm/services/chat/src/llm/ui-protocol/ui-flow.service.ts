import { BadRequestException, Injectable } from '@nestjs/common';
import type { AIUIResponse, UIAction } from './ui-types.js';

type Stage = 'init' | 'select_type' | 'fill_detail' | 'confirm' | 'result';

interface SessionContext {
  stage: Stage;
  collectedData: Record<string, unknown>;
}

const REQUIREMENT_TYPES: Record<string, string> = {
  functional: '功能需求',
  performance: '性能需求',
  security: '安全需求',
  ui_ux: 'UI/UX 需求',
};

@Injectable()
export class UIFlowService {
  private readonly sessions = new Map<string, SessionContext>();

  private getContext(sessionId: string): SessionContext {
    if (!sessionId?.trim()) {
      throw new BadRequestException('sessionId 不能为空');
    }

    let context = this.sessions.get(sessionId);

    if (!context) {
      context = {
        stage: 'init',
        collectedData: {},
      };
      this.sessions.set(sessionId, context);
    }

    return context;
  }

  handleInput(sessionId: string, input: string): AIUIResponse {
    if (!input?.trim()) {
      throw new BadRequestException('input 不能为空');
    }

    const context = this.getContext(sessionId);

    if (input.includes('需求') || input.includes('功能')) {
      context.stage = 'select_type';
      context.collectedData = {
        rawInput: input,
      };

      return this.buildSelectType(context);
    }

    return {
      message: '请选择要进行的操作。',
      components: [
        {
          type: 'action_buttons',
          title: '常用功能',
          buttons: [
            {
              id: 'new_req',
              label: '提交新需求',
              variant: 'primary',
            },
          ],
        },
      ],
      context: this.responseContext(context),
    };
  }

  handleAction(sessionId: string, action: UIAction): AIUIResponse {
    const context = this.getContext(sessionId);

    switch (context.stage) {
      case 'select_type':
        return this.onTypeSelected(context, action);

      case 'fill_detail':
        return this.onFormSubmitted(context, action);

      case 'confirm':
        return this.onConfirmation(context, action);

      case 'init':
      case 'result':
        if (
          action.componentType === 'action_buttons' &&
          action.payload.type === 'click' &&
          action.payload.actionId === 'new_req'
        ) {
          context.stage = 'select_type';
          context.collectedData = {};

          return this.buildSelectType(context);
        }

        throw new BadRequestException('当前阶段不支持该操作');
    }
  }

  private onTypeSelected(
    context: SessionContext,
    action: UIAction,
  ): AIUIResponse {
    if (
      action.componentType !== 'selection' ||
      action.payload.type !== 'select' ||
      typeof action.payload.selectedId !== 'string'
    ) {
      throw new BadRequestException('请选择一个需求类型');
    }

    const selectedId = action.payload.selectedId;

    if (!REQUIREMENT_TYPES[selectedId]) {
      throw new BadRequestException('无效的需求类型');
    }

    context.collectedData.reqType = selectedId;
    context.stage = 'fill_detail';

    return this.buildDetailForm(context);
  }

  private onFormSubmitted(
    context: SessionContext,
    action: UIAction,
  ): AIUIResponse {
    if (action.componentType !== 'form' || action.payload.type !== 'submit') {
      throw new BadRequestException('请提交需求详情表单');
    }

    const formData = action.payload.formData;

    const title =
      typeof formData.title === 'string' ? formData.title.trim() : '';

    const description =
      typeof formData.description === 'string'
        ? formData.description.trim()
        : '';

    const acceptanceCriteria =
      typeof formData.acceptanceCriteria === 'string'
        ? formData.acceptanceCriteria.trim()
        : '';

    if (!title || !description || !acceptanceCriteria) {
      throw new BadRequestException('标题、描述和验收标准不能为空');
    }

    Object.assign(context.collectedData, formData, {
      title,
      description,
      acceptanceCriteria,
    });

    context.stage = 'confirm';

    return this.buildConfirmation(context);
  }

  private onConfirmation(
    context: SessionContext,
    action: UIAction,
  ): AIUIResponse {
    if (
      action.componentType !== 'confirmation' ||
      action.payload.type !== 'confirm'
    ) {
      throw new BadRequestException('请确认或返回修改');
    }

    if (!action.payload.confirmed) {
      context.stage = 'fill_detail';

      return this.buildDetailForm(context);
    }

    context.stage = 'result';

    return this.buildResult(context);
  }

  private buildSelectType(context: SessionContext): AIUIResponse {
    return {
      message: '请先选择需求类型。',
      components: [
        {
          type: 'selection',
          title: '请选择需求类型',
          options: [
            {
              id: 'functional',
              label: '功能需求',
            },
            {
              id: 'performance',
              label: '性能需求',
            },
            {
              id: 'security',
              label: '安全需求',
            },
            {
              id: 'ui_ux',
              label: 'UI/UX 需求',
            },
          ],
          allowMultiple: false,
        },
      ],
      context: this.responseContext(context),
    };
  }

  private buildDetailForm(context: SessionContext): AIUIResponse {
    return {
      message: '请填写需求详情。',
      components: [
        {
          type: 'form',
          title: '需求详情',
          fields: [
            {
              name: 'title',
              label: '需求标题',
              type: 'input',
              required: true,
            },
            {
              name: 'description',
              label: '详细描述',
              type: 'textarea',
              required: true,
            },
            {
              name: 'priority',
              label: '优先级',
              type: 'select',
              options: [
                {
                  value: 'P0',
                  label: 'P0 - 紧急',
                },
                {
                  value: 'P1',
                  label: 'P1 - 高',
                },
                {
                  value: 'P2',
                  label: 'P2 - 中',
                },
                {
                  value: 'P3',
                  label: 'P3 - 低',
                },
              ],
            },
            {
              name: 'acceptanceCriteria',
              label: '验收标准',
              type: 'textarea',
              required: true,
            },
            {
              name: 'notes',
              label: '补充说明',
              type: 'textarea',
            },
          ],
          submitLabel: '提交',
        },
      ],
      context: this.responseContext(context),
    };
  }

  private buildConfirmation(context: SessionContext): AIUIResponse {
    const data = context.collectedData;

    const typeId = String(data.reqType ?? '');

    return {
      message: '请核对需求信息。',
      components: [
        {
          type: 'confirmation',
          title: '确认提交分析',
          summary: [
            {
              label: '需求类型',
              value: REQUIREMENT_TYPES[typeId] ?? typeId,
            },
            {
              label: '需求标题',
              value: String(data.title ?? ''),
            },
            {
              label: '优先级',
              value: String(data.priority ?? '未选择'),
            },
            {
              label: '详细描述',
              value: String(data.description ?? ''),
            },
          ],
          confirmLabel: '确认提交',
          cancelLabel: '返回修改',
        },
      ],
      context: this.responseContext(context),
    };
  }

  private buildResult(context: SessionContext): AIUIResponse {
    const data = context.collectedData;

    const typeId = String(data.reqType ?? '');

    return {
      message: '需求信息已确认，等待接入实际分析流程。',
      components: [
        {
          type: 'steps',
          steps: [
            {
              label: '选择需求类型',
              status: 'completed',
            },
            {
              label: '填写详情',
              status: 'completed',
            },
            {
              label: '确认提交',
              status: 'completed',
            },
            {
              label: '需求分析',
              status: 'current',
            },
          ],
          currentStep: 3,
        },
        {
          type: 'card',
          title: String(data.title ?? '新需求'),
          fields: [
            {
              label: '需求类型',
              value: REQUIREMENT_TYPES[typeId] ?? typeId,
            },
            {
              label: '优先级',
              value: String(data.priority ?? '未选择'),
            },
            {
              label: '状态',
              value: '待分析',
              type: 'status',
            },
          ],
        },
        {
          type: 'action_buttons',
          title: '后续操作',
          buttons: [
            {
              id: 'new_req',
              label: '再提一个需求',
              variant: 'primary',
            },
          ],
        },
      ],
      context: this.responseContext(context),
    };
  }

  private responseContext(context: SessionContext) {
    return {
      sessionStage: context.stage,
      collectedData: {
        ...context.collectedData,
      },
    };
  }
}
