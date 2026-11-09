'use client';

import { useRef, useState } from 'react';
import { ComponentRenderer } from '@/components/ai-ui/ComponentRenderer';
import type { AIUIResponse, UIAction } from '@/types/ui-types';

export function ReportView({ report }: { report: AIUIResponse }) {
  const [busy, setBusy] = useState(false); // 是否正在等待结果。
  const [answer, setAnswer] = useState(''); // 报告或指标说明。
  const [error, setError] = useState(''); // 请求失败的提示。
  const inFlight = useRef(false); // 同步记录当前请求是否进行中。

  async function handleAction(action: UIAction) {
    if (
      action.componentType !== 'selection' ||
      action.payload.type !== 'select' ||
      typeof action.payload.selectedId !== 'string' ||
      inFlight.current
    ) return;

    inFlight.current = true; // 发请求前立即标记，拦截连续点击。
    setBusy(true);
    setError('');
    setAnswer('');

    try {
      const response = await fetch('/api/ad-report/action', {
        method: 'POST', // 请求本次新增的Next.js接口。
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          campaignId: 'AD-DEMO-001', // 与本页展示的广告保持一致。
          actionId: action.payload.selectedId,
        }),
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.message || '操作失败');
      }

      if (
        typeof result.answer !== 'string' ||
        !result.answer.trim()
      ) {
        throw new Error('分析内容为空');
      }

      // 达到工具循环上限时，明确展示当前状态。
      setAnswer(
        result.status === 'limit_reached'
          ? `已达到本次工具循环上限。\n${result.answer}`
          : result.answer,
      );
    } catch (error) {
      setError(
        error instanceof Error ? error.message : '请求失败',
      );
    } finally {
      inFlight.current = false; // 成功、失败都允许后续重新操作。
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-3xl space-y-4 p-6">
      <h1 className="text-2xl font-semibold">广告运营工作台</h1>
      <p>{report.message}</p>

      {/* disabled会禁用这组内容里的原生按钮。 */}
      <fieldset
        disabled={busy}
        className="space-y-4"
        aria-busy={busy}
      >
        {report.components.map((component, index) => (
          <ComponentRenderer
            key={`${component.type}-${index}`}
            component={component}
            onAction={handleAction}
          />
        ))}
      </fieldset>

      {busy && (
        <p role="status">正在查询数据并分析，请稍候……</p>
      )}

      {error && (
        <p role="alert" className="text-red-700">{error}</p>
      )}

      {answer && (
        <section className="rounded-xl border p-4">
          <h2 className="font-semibold">处理结果</h2>

          {/* 文本按原文显示，保留换行，并由React转义。 */}
          <div className="mt-3 whitespace-pre-wrap">
            {answer}
          </div>
        </section>
      )}
    </main>
  );
}