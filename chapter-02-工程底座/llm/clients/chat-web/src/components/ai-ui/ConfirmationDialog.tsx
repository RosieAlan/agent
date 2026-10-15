import type {
  ConfirmationResponse,
  UIAction,
} from '@/types/ui-types';

export function ConfirmationDialog({
  component,
  onAction,
}: {
  component: ConfirmationResponse;
  onAction: (action: UIAction) => void;
}) {
  function respond(confirmed: boolean) {
    onAction({
      componentType: 'confirmation',
      payload: {
        type: 'confirm',
        confirmed,
      },
    });
  }

  return (
    <section className="rounded-xl border p-4">
      <h3 className="font-semibold">
        {component.title}
      </h3>

      <dl className="mt-3 space-y-2">
        {component.summary.map((item, index) => (
          <div key={`${item.label}-${index}`}>
            <dt className="text-sm text-gray-500">
              {item.label}
            </dt>
            <dd>{item.value}</dd>
          </div>
        ))}
      </dl>

      {component.warning && (
        <p className="mt-3 text-sm text-amber-700">
          {component.warning}
        </p>
      )}

      <div className="mt-4 flex gap-2">
        <button
          type="button"
          onClick={() => respond(true)}
          className="rounded-lg bg-blue-600 px-4 py-2 text-white"
        >
          {component.confirmLabel ??
            '确认'}
        </button>
        <button
          type="button"
          onClick={() => respond(false)}
          className="rounded-lg border px-4 py-2"
        >
          {component.cancelLabel ??
            '返回'}
        </button>
      </div>
    </section>
  );
}
