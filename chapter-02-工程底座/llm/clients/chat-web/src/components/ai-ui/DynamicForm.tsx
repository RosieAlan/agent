'use client';

import { useState } from 'react';
import type {
  FormResponse,
  UIAction,
} from '@/types/ui-types';

export function DynamicForm({
  component,
  initialData,
  onAction,
}: {
  component: FormResponse;
  initialData?: Record<string, unknown>;
  onAction: (action: UIAction) => void;
}) {
  const [values, setValues] = useState<
    Record<string, string>
  >(() =>
    Object.fromEntries(
      component.fields.map((field) => [
        field.name,
        String(initialData?.[field.name] ?? ''),
      ]),
    ),
  );

  function update(name: string, value: string) {
    setValues((current) => ({
      ...current,
      [name]: value,
    }));
  }

  return (
    <form
      className="space-y-4 rounded-xl border p-4"
      onSubmit={(event) => {
        event.preventDefault();
        onAction({
          componentType: 'form',
          payload: {
            type: 'submit',
            formData: values,
          },
        });
      }}
    >
      <h3 className="font-semibold">
        {component.title}
      </h3>
      {component.description && (
        <p className="text-sm text-gray-600">
          {component.description}
        </p>
      )}

      {component.fields.map((field) => (
        <label
          key={field.name}
          className="block space-y-1"
        >
          <span className="text-sm font-medium">
            {field.label}
            {field.required && ' *'}
          </span>

          {field.type === 'textarea' ? (
            <textarea
              required={Boolean(field.required)}
              value={values[field.name] ?? ''}
              placeholder={field.placeholder ?? ''}
              onChange={(event) =>
                update(
                  field.name,
                  event.target.value,
                )
              }
              className="w-full rounded-lg border p-2"
              rows={3}
            />
          ) : field.type === 'select' ? (
            <select
              required={Boolean(field.required)}
              value={values[field.name] ?? ''}
              onChange={(event) =>
                update(
                  field.name,
                  event.target.value,
                )
              }
              className="w-full rounded-lg border p-2"
            >
              <option value="">请选择</option>
              {field.options?.map((option) => (
                <option
                  key={option.value}
                  value={option.value}
                >
                  {option.label}
                </option>
              ))}
            </select>
          ) : (
            <input
              type={
                field.type === 'number'
                  ? 'number'
                  : field.type === 'date'
                    ? 'date'
                    : 'text'
              }
              required={Boolean(field.required)}
              value={values[field.name] ?? ''}
              placeholder={field.placeholder ?? ''}
              onChange={(event) =>
                update(
                  field.name,
                  event.target.value,
                )
              }
              className="w-full rounded-lg border p-2"
            />
          )}
        </label>
      ))}

      <button
        type="submit"
        className="rounded-lg bg-blue-600 px-4 py-2 text-white"
      >
        {component.submitLabel ?? '提交'}
      </button>
    </form>
  );
}
