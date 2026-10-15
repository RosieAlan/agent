import type {
  ActionButtonsResponse,
  UIAction,
} from '@/types/ui-types';

export function ActionButtons({
  component,
  onAction,
}: {
  component: ActionButtonsResponse;
  onAction: (action: UIAction) => void;
}) {
  return (
    <section className="rounded-xl border p-4">
      {component.title && (
        <h3 className="mb-3 font-semibold">
          {component.title}
        </h3>
      )}
      <div className="flex flex-wrap gap-2">
        {component.buttons.map((button) => (
          <button
            key={button.id}
            type="button"
            onClick={() =>
              onAction({
                componentType:
                  'action_buttons',
                payload: {
                  type: 'click',
                  actionId:
                    button.id,
                },
              })
            }
            className="rounded-lg border px-3 py-2 hover:border-blue-500"
          >
            {button.icon} {button.label}
          </button>
        ))}
      </div>
    </section>
  );
}
