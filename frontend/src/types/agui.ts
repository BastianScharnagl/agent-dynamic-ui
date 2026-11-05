export interface GuiElement {
  id: string;
  element: 'text_input' | 'number_input' | 'textarea' | 'select' | 'date_picker' | 'checkbox';
  label: string;
  placeholder?: string;
  required?: boolean;
  options?: string[];
  default_value?: string;
  validation?: {
    min?: number;
    max?: number;
    pattern?: string;
    error_message?: string;
  };
  visibility?: {
    depends_on: string;
    operator: 'equals' | 'not_equals' | 'greater_than' | 'less_than' | 'contains';
    value: string;
  };
}

export interface DynamicGuiPayload {
  form_id: string;
  headline: string;
  description?: string;
  elements: GuiElement[];
  submit_label: string;
}

export interface UIRenderEvent {
  callId: string;
  toolName: string;
  component: DynamicGuiPayload;
}