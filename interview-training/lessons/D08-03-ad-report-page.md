# D08-03：广告报表页面接入。日期：11/04

原课6.4.1–6.4.3；复用ComponentRenderer/InfoCard/SelectionCard/UIAction，页面级新增ad-report两文件。学生自行写入，教师只维护候选讲义。现有共享组件与ui-demo保留。

调用：浏览器3002/ad-report → Next服务端page.tsx fetch → Python8000/ui/ads/report/AD-DEMO-001 → 原D07数据库查询 → UIResponse → ReportView → ComponentRenderer → InfoCard/SelectionCard。点击回调只显示操作编号，业务执行及审批下一块实现。Next服务端代发请求，浏览器跨源CORS不参与此GET；身份仍为本地固定演练，真实登录授权后续验收。

新增src/app/ad-report/page.tsx：
```tsx
import type { AIUIResponse } from '@/types/ui-types';
import { ReportView } from './report-view';

export default async function AdReportPage() {
  let report: AIUIResponse;
  try {
    const baseUrl = process.env.PYTHON_API_BASE_URL || 'http://127.0.0.1:8000';
    const response = await fetch(
      `${baseUrl}/ui/ads/report/AD-DEMO-001`,
      { cache: 'no-store', signal: AbortSignal.timeout(5000) },
    ); // Next.js服务端请求Python；每次访问取最新数据，最多等待5秒。
    if (!response.ok) {
      throw new Error(`Python HTTP ${response.status}`);
    } // fetch遇到404/500仍会返回Response，需要主动检查状态。
    report = await response.json(); // 读取上一块已经过后端校验的JSON。
  } catch (error) {
    console.error('[ad-report] load failed', error); // 详细原因留在Next.js终端。
    return (
      <main className="mx-auto max-w-3xl p-6">
        <h1 className="text-xl font-semibold">广告报表</h1>
        <p role="alert">报表加载失败，请确认Python服务已启动，再刷新页面。</p>
      </main>
    );
  }
  return <ReportView report={report} />; // 把可序列化的数据传给交互组件。
}
```

新增同目录report-view.tsx：
```tsx
'use client'; // 本文件处理浏览器点击和页面状态。

import { useState } from 'react';
import { ComponentRenderer } from '@/components/ai-ui/ComponentRenderer';
import type { AIUIResponse, UIAction } from '@/types/ui-types';

export function ReportView({ report }: { report: AIUIResponse }) {
  const [selectedId, setSelectedId] = useState(''); // 保存最近点击的操作编号。

  function handleAction(action: UIAction) {
    if (
      action.componentType === 'selection' &&
      action.payload.type === 'select' &&
      typeof action.payload.selectedId === 'string'
    ) {
      setSelectedId(action.payload.selectedId); // 例如generate_report。
    }
  }

  return (
    <main className="mx-auto max-w-3xl space-y-4 p-6">
      <h1 className="text-2xl font-semibold">广告运营工作台</h1>
      <p>{report.message}</p>
      {report.components.map((component, index) => (
        <ComponentRenderer
          key={`${component.type}-${index}`}
          component={component}
          onAction={handleAction}
        />
      ))} {/* 现有组件内部根据type选择InfoCard或SelectionCard。 */}
      {selectedId && (
        <p role="status" className="rounded-lg border p-3">
          已收到操作：{selectedId}。本块只记录选择，业务请求下一块接入。
        </p>
      )}
    </main>
  );
}
```

新API：async服务端页面可await fetch；use client声明交互边界；cache:no-store每次请求取数据；AbortSignal.timeout(5000)限制5秒等待；response.ok检查2xx；response.json读取响应体；TS类型注解帮助编译期检查，运行时协议校验在Python完成。当前部署同机默认127.0.0.1，异机部署用Next服务端PYTHON_API_BASE_URL指定可信后端地址。

启动：Python项目.\dev.cmd；前端clients/chat-web中bunx --no-install next dev --port 3002，直接启动避免原dev脚本wait-on4001。访问/ad-report看100.00/250.00/2.50，点击两选项观察操作id。8000停机应显示加载失败；3002已有服务可直接访问。界面浏览器证据待学生提交。

必背：后端返回受控组件数据，前端按type复用组件；点击变成UIAction，后端仍须校验操作、身份和当前状态。TS类型检查与后端运行时校验分别负责开发阶段及实际数据约束。独立题：把固定活动编号改为另一个已存在编号，解释请求发生在Next服务端；后续动态输入独立扩展。

依据：Next官方server-and-client-components与fetching-data，已核对本地Next16.2.3/React19.2.4；本地附带docs缺失，使用官方文档。D08-02用户已交200/card/selection，计当前运行证据；D08-03候选验证与学生运行分别登记。

