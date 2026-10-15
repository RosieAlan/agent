import type {
  UIAction,
  UIResponse,
} from '@/types/ui-types';
import { SelectionCard } from './SelectionCard';
import { DynamicForm } from './DynamicForm';
import { ConfirmationDialog } from './ConfirmationDialog';
import { InfoCard } from './InfoCard';
import { StepsProgress } from './StepsProgress';
import { DataTable } from './DataTable';
import { ActionButtons } from './ActionButtons';

export function ComponentRenderer({
  component,
  initialData,
  onAction,
}: {
  component: UIResponse;
  initialData?: Record<string, unknown>;
  onAction: (action: UIAction) => void;
}) {
  switch (component.type) {
    case 'text':
      return (
        <div className="whitespace-pre-wrap">
          {component.content}
        </div>
      );

    case 'selection':
      return (
        <SelectionCard
          component={component}
          onAction={onAction}
        />
      );

    case 'form':
      return (
        <DynamicForm
          component={component}
          initialData={initialData}
          onAction={onAction}
        />
      );

    case 'confirmation':
      return (
        <ConfirmationDialog
          component={component}
          onAction={onAction}
        />
      );

    case 'card':
      return (
        <InfoCard
          component={component}
          onAction={onAction}
        />
      );

    case 'steps':
      return (
        <StepsProgress
          component={component}
        />
      );

    case 'table':
      return (
        <DataTable
          component={component}
          onAction={onAction}
        />
      );

    case 'action_buttons':
      return (
        <ActionButtons
          component={component}
          onAction={onAction}
        />
      );

    default: {
      const unknown = component as {
        type: string;
      };

      return (
        <div className="rounded-lg border p-3 text-sm text-gray-500">
          不支持的组件类型：
          {unknown.type}
        </div>
      );
    }
  }
}
