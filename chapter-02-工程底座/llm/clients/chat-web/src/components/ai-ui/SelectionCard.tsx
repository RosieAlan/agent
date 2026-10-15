'use client';

import { useState } from 'react';
import type {
  SelectionResponse,
  UIAction,
} from '@/types/ui-types';

export function SelectionCard({
  component,
  onAction,
}: {
  component: SelectionResponse;
  onAction: (action: UIAction) => void;
}) {
  const [selected, setSelected] =
    useState<string[]>([]);

  function choose(id: string) {
    if (!component.allowMultiple) {
      onAction({
        componentType: 'selection',
        payload: {
          type: 'select',
          selectedId: id,
        },
      });
      return;
    }

    setSelected((current) =>
      current.includes(id)
        ? current.filter((item) => item !== id)
        : [...current, id],
    );
  }

  return (
    <section className="rounded-xl border p-4">
      <h3 className="font-semibold">
        {component.title}
      </h3>
      {component.description && (
        <p className="mt-1 text-sm text-gray-600">
          {component.description}
        </p>
      )}

      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        {component.options.map((option) => (
          <button
            key={option.id}
            type="button"
            disabled={Boolean(option.disabled)}
            onClick={() => choose(option.id)}
            className={`rounded-lg border p-3 text-left hover:border-blue-500 disabled:opacity-50 ${
              selected.includes(option.id)
                ? 'border-blue-500 bg-blue-50'
                : ''
            }`}
          >
            <div className="font-medium">
              {option.icon} {option.label}
            </div>
            {option.description && (
              <p className="mt-1 text-sm text-gray-600">
                {option.description}
              </p>
            )}
          </button>
        ))}
      </div>

      {component.allowMultiple && (
        <button
          type="button"
          disabled={selected.length === 0}
          onClick={() =>
            onAction({
              componentType: 'selection',
              payload: {
                type: 'select',
                selectedId: selected,
              },
            })
          }
          className="mt-3 rounded-lg bg-blue-600 px-4 py-2 text-white disabled:opacity-50"
        >
          确认选择
        </button>
      )}
    </section>
  );
}
