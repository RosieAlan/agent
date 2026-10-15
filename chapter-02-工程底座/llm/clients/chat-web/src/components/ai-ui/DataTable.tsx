import type {
  TableResponse,
  UIAction,
} from '@/types/ui-types';

export function DataTable({
  component,
  onAction,
}: {
  component: TableResponse;
  onAction: (action: UIAction) => void;
}) {
  return (
    <div className="overflow-x-auto rounded-xl border">
      <table className="w-full text-left text-sm">
        <thead className="bg-gray-50">
          <tr>
            {component.columns.map((column) => (
              <th
                key={column.key}
                className="p-3"
              >
                {column.label}
              </th>
            ))}
            {component.selectable && (
              <th className="p-3">操作</th>
            )}
          </tr>
        </thead>
        <tbody>
          {component.rows.map((row, index) => (
            <tr
              key={index}
              className="border-t"
            >
              {component.columns.map((column) => (
                <td
                  key={column.key}
                  className="p-3"
                >
                  {row[column.key] ?? ''}
                </td>
              ))}
              {component.selectable && (
                <td className="p-3">
                  <button
                    type="button"
                    onClick={() =>
                      onAction({
                        componentType:
                          'table',
                        payload: {
                          type:
                            'row_select',
                          rowIndex:
                            index,
                        },
                      })
                    }
                    className="text-blue-600"
                  >
                    选择
                  </button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
