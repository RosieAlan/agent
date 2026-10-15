import type {
  CardResponse,
  UIAction,
} from '@/types/ui-types';

export function InfoCard({
  component,
  onAction,
}: {
  component: CardResponse;
  onAction: (action: UIAction) => void;
}) {
  return (
    <section className="rounded-xl border p-4">
      <h3 className="font-semibold">
        {component.icon} {component.title}
      </h3>
      {component.subtitle && (
        <p className="text-sm text-gray-600">
          {component.subtitle}
        </p>
      )}

      <dl className="mt-3 grid gap-3 sm:grid-cols-2">
        {component.fields.map((field, index) => (
          <div
            key={`${field.label}-${index}`}
          >
            <dt className="text-sm text-gray-500">
              {field.label}
            </dt>
            <dd>{field.value}</dd>
          </div>
        ))}
      </dl>

      {component.actions && (
        <div className="mt-4 flex gap-2">
          {component.actions.map((action) => (
            <button
              key={action.id}
              type="button"
              onClick={() =>
                onAction({
                  componentType: 'card',
                  payload: {
                    type: 'click',
                    actionId: action.id,
                  },
                })
              }
              className="rounded-lg border px-3 py-2"
            >
              {action.label}
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
