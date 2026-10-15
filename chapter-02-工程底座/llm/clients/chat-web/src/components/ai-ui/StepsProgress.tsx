import type {
  StepsResponse,
} from '@/types/ui-types';

export function StepsProgress({
  component,
}: {
  component: StepsResponse;
}) {
  return (
    <ol className="rounded-xl border p-4">
      {component.steps.map((step, index) => (
        <li
          key={`${step.label}-${index}`}
          className="flex items-center gap-3 py-2"
        >
          <span
            className={`flex h-7 w-7 items-center justify-center rounded-full text-sm ${
              step.status === 'completed'
                ? 'bg-green-100 text-green-700'
                : step.status === 'current'
                  ? 'bg-blue-100 text-blue-700'
                  : 'bg-gray-100 text-gray-500'
            }`}
          >
            {index + 1}
          </span>
          <span>{step.label}</span>
          <span className="ml-auto text-xs text-gray-500">
            {step.status}
          </span>
        </li>
      ))}
    </ol>
  );
}
