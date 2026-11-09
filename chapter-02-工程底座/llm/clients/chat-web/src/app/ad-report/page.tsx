import type { AIUIResponse } from '@/types/ui-types';
import { ReportView } from './report-view';

export default async function AdReportPage() {
  let report: AIUIResponse; // 保存取得的报表组件数据。

  try {
    // 本地默认请求8000；部署时可以通过服务端环境变量调整地址。
    const baseUrl =
      process.env.PYTHON_API_BASE_URL || 'http://127.0.0.1:8000';

    const response = await fetch(
      `${baseUrl}/ui/ads/report/AD-DEMO-001`,
      {
        cache: 'no-store', // 每次访问重新读取报表。
        signal: AbortSignal.timeout(5000), // 最多等待5秒。
      },
    );

    if (!response.ok) {
      // fetch收到404、500时仍返回Response，需要检查状态。
      throw new Error(`Python HTTP ${response.status}`);
    }

    // 读取上一块已经过Python校验的JSON。
    report = await response.json();
  } catch (error) {
    // 详细原因打印在Next.js启动终端，页面显示操作提示。
    console.error('[ad-report] load failed', error);

    return (
      <main className="mx-auto max-w-3xl p-6">
        <h1 className="text-xl font-semibold">广告报表</h1>
        <p role="alert">
          报表加载失败，请确认Python服务已启动，再刷新页面。
        </p>
      </main>
    );
  }

  // 将数据交给下面的交互组件。
  return <ReportView report={report} />;
}