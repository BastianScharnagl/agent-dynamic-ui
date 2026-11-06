import React, { useState } from 'react';

export interface ValidationRule {
  min?: number;
  max?: number;
  pattern?: string;
  error_message?: string;
}

export interface VisibilityCondition {
  depends_on: string;
  operator: 'equals' | 'not_equals' | 'greater_than' | 'less_than' | 'contains';
  value: string;
}

export interface GuiElement {
  id: string;
  element: 'text_input' | 'number_input' | 'textarea' | 'select' | 'date_picker' | 'checkbox';
  label: string;
  placeholder?: string;
  required?: boolean;
  options?: string[];
  default_value?: any;
  validation?: ValidationRule;
  visibility?: VisibilityCondition;
}

export interface DynamicGuiPayload {
  form_id: string;
  headline: string;
  description?: string;
  elements: GuiElement[];
  submit_label: string;
}

export const DynamicForm: React.FC<{
  data: DynamicGuiPayload;
  onSubmit: (formData: Record<string, any>) => void;
}> = ({ data, onSubmit }) => {
  // 1. Initialer State aus default_value aller Elemente befüllen
  const [formValues, setFormValues] = useState<Record<string, any>>(() => {
    const initial: Record<string, any> = {};
    data.elements.forEach(el => {
      if (el.default_value !== undefined && el.default_value !== null) {
        initial[el.id] = el.default_value;
      } else if (el.element === 'checkbox') {
        initial[el.id] = false;
      } else {
        initial[el.id] = '';
      }
    });
    return initial;
  });

  const [errors, setErrors] = useState<Record<string, string>>({});

  // 2. Bedingte Sichtbarkeit prüfen
  const isElementVisible = (visibility?: VisibilityCondition): boolean => {
    if (!visibility) return true;

    const sourceValue = formValues[visibility.depends_on];
    if (sourceValue === undefined || sourceValue === null || sourceValue === '') return false;

    const targetVal = visibility.value;

    switch (visibility.operator) {
      case 'equals':
        return String(sourceValue) === targetVal;
      case 'not_equals':
        return String(sourceValue) !== targetVal;
      case 'greater_than':
        return Number(sourceValue) > Number(targetVal);
      case 'less_than':
        return Number(sourceValue) < Number(targetVal);
      case 'contains':
        return String(sourceValue).toLowerCase().includes(targetVal.toLowerCase());
      default:
        return true;
    }
  };

  // 3. Validierungslogik
  const validateField = (el: GuiElement, val: any): string | null => {
    if (!isElementVisible(el.visibility)) return null;

    // Checkbox Pflichtfeldprüfung (muss true sein)
    if (el.element === 'checkbox') {
      if (el.required && val !== true) {
        return `${el.label} muss bestätigt werden.`;
      }
      return null;
    }

    // Allgemeine Pflichtfeldprüfung
    if (el.required && (val === undefined || val === '' || val === null)) {
      return `${el.label} ist ein Pflichtfeld.`;
    }

    if (!val && val !== 0) return null;

    const rule = el.validation;
    if (!rule) return null;

    if (el.element === 'number_input') {
      const num = Number(val);
      if (rule.min !== undefined && num < rule.min) {
        return rule.error_message || `Mindestwert ist ${rule.min}.`;
      }
      if (rule.max !== undefined && num > rule.max) {
        return rule.error_message || `Maximalwert ist ${rule.max}.`;
      }
    } else if (typeof val === 'string') {
      if (rule.min !== undefined && val.length < rule.min) {
        return rule.error_message || `Mindestens ${rule.min} Zeichen erforderlich.`;
      }
      if (rule.max !== undefined && val.length > rule.max) {
        return rule.error_message || `Maximal ${rule.max} Zeichen erlaubt.`;
      }
      if (rule.pattern) {
        const regex = new RegExp(rule.pattern);
        if (!regex.test(val)) {
          return rule.error_message || 'Format ist ungültig.';
        }
      }
    }

    return null;
  };

  const handleInputChange = (el: GuiElement, value: any) => {
    setFormValues(prev => ({ ...prev, [el.id]: value }));
    const error = validateField(el, value);
    setErrors(prev => ({ ...prev, [el.id]: error || '' }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const newErrors: Record<string, string> = {};
    let isValid = true;

    data.elements.forEach(el => {
      if (isElementVisible(el.visibility)) {
        const err = validateField(el, formValues[el.id]);
        if (err) {
          newErrors[el.id] = err;
          isValid = false;
        }
      }
    });

    setErrors(newErrors);

    if (isValid) {
      const sanitizedValues: Record<string, any> = {};
      data.elements.forEach(el => {
        if (isElementVisible(el.visibility) && formValues[el.id] !== undefined) {
          sanitizedValues[el.id] = formValues[el.id];
        }
      });
      onSubmit(sanitizedValues);
    }
  };

  return (
    <form onSubmit={handleSubmit} style={{ background: '#fff', padding: '24px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
      <h3 style={{ margin: '0 0 8px 0', color: '#0f172a' }}>{data.headline}</h3>
      {data.description && (
        <p style={{ color: '#475569', fontSize: '14px', whiteSpace: 'pre-line', marginBottom: '20px' }}>
          {data.description}
        </p>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {data.elements.map(el => {
          if (!isElementVisible(el.visibility)) return null;

          const error = errors[el.id];
          const isInvalid = !!error;

          return (
            <div key={el.id} style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              
              {/* Checkbox separat rendern (Label rechts) */}
              {el.element === 'checkbox' ? (
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '14px' }}>
                  <input
                    type="checkbox"
                    checked={!!formValues[el.id]}
                    onChange={e => handleInputChange(el, e.target.checked)}
                    style={{ width: '16px', height: '16px' }}
                  />
                  <span>
                    {el.label} {el.required && <span style={{ color: '#ef4444' }}>*</span>}
                  </span>
                </label>
              ) : (
                <label style={{ fontSize: '14px', fontWeight: 600, color: '#334155' }}>
                  {el.label} {el.required && <span style={{ color: '#ef4444' }}>*</span>}
                </label>
              )}

              {/* Text Input */}
              {el.element === 'text_input' && (
                <input
                  type="text"
                  placeholder={el.placeholder}
                  value={formValues[el.id] || ''}
                  onChange={e => handleInputChange(el, e.target.value)}
                  style={{ padding: '8px 12px', border: `1px solid ${isInvalid ? '#ef4444' : '#cbd5e1'}`, borderRadius: '6px' }}
                />
              )}

              {/* Number Input */}
              {el.element === 'number_input' && (
                <input
                  type="number"
                  step="any"
                  placeholder={el.placeholder}
                  value={formValues[el.id] !== undefined ? formValues[el.id] : ''}
                  onChange={e => handleInputChange(el, e.target.value ? Number(e.target.value) : '')}
                  style={{ padding: '8px 12px', border: `1px solid ${isInvalid ? '#ef4444' : '#cbd5e1'}`, borderRadius: '6px' }}
                />
              )}

              {/* Dropdown Select */}
              {el.element === 'select' && (
                <select
                  value={formValues[el.id] || ''}
                  onChange={e => handleInputChange(el, e.target.value)}
                  style={{ padding: '8px 12px', border: `1px solid ${isInvalid ? '#ef4444' : '#cbd5e1'}`, borderRadius: '6px', background: '#fff' }}
                >
                  <option value="" disabled>Bitte wählen...</option>
                  {el.options?.map((opt, i) => (
                    <option key={i} value={opt}>{opt}</option>
                  ))}
                </select>
              )}

              {/* Date Picker */}
              {el.element === 'date_picker' && (
                <input
                  type="date"
                  value={formValues[el.id] || ''}
                  onChange={e => handleInputChange(el, e.target.value)}
                  style={{ padding: '8px 12px', border: `1px solid ${isInvalid ? '#ef4444' : '#cbd5e1'}`, borderRadius: '6px' }}
                />
              )}

              {/* Textarea */}
              {el.element === 'textarea' && (
                <textarea
                  rows={3}
                  placeholder={el.placeholder}
                  value={formValues[el.id] || ''}
                  onChange={e => handleInputChange(el, e.target.value)}
                  style={{ padding: '8px 12px', border: `1px solid ${isInvalid ? '#ef4444' : '#cbd5e1'}`, borderRadius: '6px', resize: 'vertical' }}
                />
              )}

              {/* Validierungsfehlermeldung */}
              {error && <span style={{ color: '#ef4444', fontSize: '12px' }}>{error}</span>}
            </div>
          );
        })}
      </div>

      <button
        type="submit"
        style={{
          marginTop: '24px',
          width: '100%',
          padding: '12px',
          background: '#2563eb',
          color: '#fff',
          fontWeight: 600,
          border: 'none',
          borderRadius: '6px',
          cursor: 'pointer'
        }}
      >
        {data.submit_label}
      </button>
    </form>
  );
};