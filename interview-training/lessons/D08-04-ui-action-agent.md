# D08-04：操作回传与真实Agent调用。日期：11/04

原6.3.3/6.4.3：复用Python /ads/chat → run_ad_tool → 工具查PG → 模型答复。新增Next src/app/api/ad-report/action/route.ts，修改ad-report/report-view.tsx；共享组件/Python源码保持。此块两个选项均调用真实模型，新增token消耗由学生点击验收。先输入校验再请求；固定任务映射和操作白名单；同源检查/125秒转发上限/错误脱敏/空回复502；客户端useRef同步防重复+fieldset禁用并最终解锁。防重复限当前页面，跨窗口/重试幂等与服务端限流仍待专门单元；断开转发请求不等于Python模型任务已停。当前固定user/store与合成数据，登录授权/动作持久化/审批状态后续接入，当前为只读分析。

新增route.ts：
```ts
export const runtime = 'nodejs'; // 在Next.js服务端运行。

export async function POST(request: Request) {
  const origin = request.headers.get('origin');
  if (origin && origin !== new URL(request.url).origin) {
    return Response.json({ message: '请从当前页面提交' }, { status: 403 });
  }

  let body;
  try {
    body = await request.json(); // 读取浏览器提交的JSON。
  } catch {
    return Response.json({ message: '请求需要JSON格式' }, { status: 400 });
  }

  const tasks: Record<string, string> = {
    generate_report: '生成简洁广告分析报告，包含指标、数据局限、待确认信息与建议。',
    explain_metrics: '解释花费、归因销售额和ROAS，结合本次报表说明计算过程。',
  }; // 后端固定任务说明，页面只提交操作编号。

  if (
    !body || typeof body !== 'object' ||
    typeof body.campaignId !== 'string' ||
    !/^AD-[A-Za-z0-9-]{1,60}$/.test(body.campaignId) ||
    typeof body.actionId !== 'string' ||
    !Object.hasOwn(tasks, body.actionId)
  ) {
    return Response.json({ message: '广告编号或操作编号无效' }, { status: 422 });
  }

  const timeout = AbortSignal.timeout(125_000); // 覆盖已有工具循环的等待时间。
  try {
    const baseUrl = process.env.PYTHON_API_BASE_URL || 'http://127.0.0.1:8000';
    const response = await fetch(`${baseUrl}/ads/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        input: `广告活动${body.campaignId}。${tasks[body.actionId]}先用工具查数据，标明来源。盈利判断说明所需毛利及其他费用；本次只查询和分析。`,
      }), // 将已验证的操作转换成Python已有接口接收的input。
      cache: 'no-store',
      signal: AbortSignal.any([request.signal, timeout]),
    });

    if (!response.ok) {
      return Response.json(
        { message: '分析暂时失败，请查看Python日志后重试' },
        { status: response.status >= 500 ? response.status : 502 },
      );
    }

    const result = await response.json();
    if (
      !result || typeof result.answer !== 'string' || !result.answer.trim() ||
      !['completed', 'limit_reached'].includes(result.status)
    ) {
      return Response.json({ message: '分析结果格式异常或内容为空' }, { status: 502 });
    }
    return Response.json({ status: result.status, answer: result.answer });
  } catch (error) {
    console.error('[ad-action] request failed', error);
    return Response.json(
      { message: timeout.aborted ? '分析等待超时，请稍后重试' : '分析服务连接失败' },
      { status: timeout.aborted ? 504 : 503 },
    );
  }
}
```

替换report-view.tsx：
```tsx
'use client';

import { useRef, useState } from 'react';
import { ComponentRenderer } from '@/components/ai-ui/ComponentRenderer';
import type { AIUIResponse, UIAction } from '@/types/ui-types';

export function ReportView({ report }: { report: AIUIResponse }) {
  const [busy, setBusy] = useState(false); // 控制加载提示。
  const [answer, setAnswer] = useState(''); // Python返回的报告或指标说明。
  const [error, setError] = useState(''); // 当前请求的错误提示。
  const inFlight = useRef(false); // 同步拦截本页面连续点击。

  async function handleAction(action: UIAction) {
    if (
      action.componentType !== 'selection' ||
      action.payload.type !== 'select' ||
      typeof action.payload.selectedId !== 'string' ||
      inFlight.current
    ) return;

    inFlight.current = true; // 在发请求前立即上锁。
    setBusy(true);
    setError('');
    setAnswer('');

    try {
      const response = await fetch('/api/ad-report/action', {
        method: 'POST', // 浏览器请求同一个3002服务。
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          campaignId: 'AD-DEMO-001', // 与本页加载的广告编号保持一致。
          actionId: action.payload.selectedId, // 例如generate_report。
        }),
      });

      const result = await response.json();
      if (!response.ok) {
        throw new Error(result.message || '操作失败');
      }
      if (typeof result.answer !== 'string' || !result.answer.trim()) {
        throw new Error('分析内容为空');
      }
      setAnswer(
        result.status === 'limit_reached'
          ? `已达到本次工具循环上限。\n${result.answer}`
          : result.answer,
      );
    } catch (error) {
      setError(error instanceof Error ? error.message : '请求失败');
    } finally {
      inFlight.current = false; // 成功或失败后都允许重新操作。
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-3xl space-y-4 p-6">
      <h1 className="text-2xl font-semibold">广告运营工作台</h1>
      <p>{report.message}</p>
      <fieldset disabled={busy} className="space-y-4" aria-busy={busy}>
        {report.components.map((component, index) => (
          <ComponentRenderer
            key={`${component.type}-${index}`}
            component={component}
            onAction={handleAction}
          />
        ))}
      </fieldset>
      {busy && <p role="status">正在查询数据并分析，请稍候……</p>}
      {error && <p role="alert" className="text-red-700">{error}</p>}
      {answer && (
        <section className="rounded-xl border p-4">
          <h2 className="font-semibold">处理结果</h2>
          <div className="mt-3 whitespace-pre-wrap">{answer}</div>
        </section>
      )}
    </main>
  );
}
```

当前输入campaignId/actionId → Next固定任务文本input → Python status/answer/tool_results → Next仅返回status/answer → 页面显示。route.ts是Next HTTP接口文件约定，POST命名函数处理POST；请求发生在点击时。useRef保留可同步修改的引用，避免React渲染前连续点击发两次；useState驱动加载/结果/错误显示；fieldset.disabled禁用内部原生按钮。文本显示保持React转义，Markdown当前以原文字显示。

启动命令修正：前端nvm use22.19.0后node .\node_modules\next\dist\bin\next dev --webpack --port3002（参数间留空格）；上一块bunx --bun启动在此Windows引发子进程路径被识别Git依赖，机器默认Node14另不满足Next最低20.9，用户已切22。Python .\dev.cmd。已有服务保存文件自动更新即可。验收：两个按钮各请求/api/ad-report/action与/ads/chat；展示合成来源及ROAS，快速重复点击同一页仅一个请求；非法action422；服务关闭503并可恢复重试。生成报告没有预算写入副作用，ROAS不能单独证明盈利。浏览器真实模型输出等待学生。

必背答案：UIAction描述用户操作，服务端校验操作编号再选择固定处理；模型负责查询分析，授权/预算修改/状态推进由受控代码验证。当前代理为前端服务端接口，业务Agent仍在Python。生产登录/数据库任务与幂等按后续既定教学接入。

