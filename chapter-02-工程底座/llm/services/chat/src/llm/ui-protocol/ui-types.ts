export interface TextResponse {
  type: 'text';
  content: string;
}

export interface SelectionOption {
  id: string;
  label: string;
  description?: string | null;
  icon?: string | null;
  disabled?: boolean | null;
}

export interface SelectionResponse {
  type: 'selection';
  title: string;
  description?: string | null;
  options: SelectionOption[];
  allowMultiple?: boolean | null;
}

export interface FormField {
  name: string;
  label: string;
  type:
    | 'input'
    | 'textarea'
    | 'select'
    | 'date'
    | 'number';
  required?: boolean | null;
  placeholder?: string | null;
  options?: Array<{
    value: string;
    label: string;
  }> | null;
}

export interface FormResponse {
  type: 'form';
  title: string;
  description?: string | null;
  fields: FormField[];
  submitLabel?: string | null;
}

export interface ConfirmationResponse {
  type: 'confirmation';
  title: string;
  summary: Array<{
    label: string;
    value: string;
  }>;
  warning?: string | null;
  confirmLabel?: string | null;
  cancelLabel?: string | null;
}

export interface CardResponse {
  type: 'card';
  title: string;
  subtitle?: string | null;
  icon?: string | null;
  fields: Array<{
    label: string;
    value: string;
    type?: 'text' | 'status' | 'date' | null;
  }>;
  actions?: Array<{
    id: string;
    label: string;
    variant?: 'primary' | 'secondary' | 'ghost' | null;
  }> | null;
}

export interface StepsResponse {
  type: 'steps';
  steps: Array<{
    label: string;
    status: 'pending' | 'current' | 'completed';
  }>;
  currentStep: number;
}

export interface TableResponse {
  type: 'table';
  columns: Array<{
    key: string;
    label: string;
  }>;
  rows: Array<Record<string, string>>;
  selectable?: boolean | null;
}

export interface ActionButtonsResponse {
  type: 'action_buttons';
  title?: string | null;
  buttons: Array<{
    id: string;
    label: string;
    icon?: string | null;
    variant?: 'primary' | 'secondary' | 'ghost' | null;
  }>;
  layout?: 'horizontal' | 'vertical' | null;
}

export type UIResponse =
  | TextResponse
  | SelectionResponse
  | FormResponse
  | ConfirmationResponse
  | CardResponse
  | StepsResponse
  | TableResponse
  | ActionButtonsResponse;

export interface AIUIResponse {
  message: string;
  components: UIResponse[];
  context?: {
    sessionStage?: string | null;
    collectedData?: Record<string, unknown> | null;
  } | null;
}

export interface UIAction {
  componentType: UIResponse['type'];
  payload:
    | {
        type: 'select';
        selectedId: string | string[];
      }
    | {
        type: 'submit';
        formData: Record<string, unknown>;
      }
    | {
        type: 'confirm';
        confirmed: boolean;
      }
    | {
        type: 'click';
        actionId: string;
      }
    | {
        type: 'row_select';
        rowIndex: number;
      };
}
