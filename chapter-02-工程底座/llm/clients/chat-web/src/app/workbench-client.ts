export interface ProgressEvent {
  step: string;
  label: string;
  status: 'running' | 'completed' | 'failed';
}

export interface AnalysisResult {
  status: 'completed' | 'need_clarification' | 'failed';
  report?: string;
  error?: string;
  clarificationQuestions?: string[];
  activeExperts?: string[];
  expertAnalyses?: Record<string, string>;
  usedAgents?: string[];
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/workbench/${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  });
  const payload = response.status === 204 ? undefined : await response.json();
  if (!response.ok) {
    if (response.status === 401) window.dispatchEvent(new Event('workbench:unauthorized'));
    throw new Error(Array.isArray(payload?.message)
      ? payload.message.join('；') : payload?.message || `请求失败（${response.status}）`);
  }
  return payload as T;
}

export async function readAnalysisStream(
  response: Response,
  onProgress: (event: ProgressEvent) => void,
): Promise<AnalysisResult> {
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    if (response.status === 401 && typeof window !== 'undefined') {
      window.dispatchEvent(new Event('workbench:unauthorized'));
    }
    throw new Error(error.message || `分析请求失败（${response.status}）`);
  }
  if (!response.body) throw new Error('连接未返回数据，请重试');
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let pending = '';
  try {
    while (true) {
      const { value, done } = await reader.read();
      pending += decoder.decode(value, { stream: !done });
      let separator: RegExpExecArray | null;
      while ((separator = /\r?\n\r?\n/.exec(pending))) {
        const frame = pending.slice(0, separator.index);
        pending = pending.slice(separator.index + separator[0].length);
        let event = '';
        const data: string[] = [];
        for (const line of frame.split(/\r?\n/)) {
          if (line.startsWith('event:')) event = line.slice(6).trim();
          if (line.startsWith('data:')) data.push(line.slice(5).trimStart());
        }
        if (!data.length) continue;
        const payload = JSON.parse(data.join('\n'));
        if (event === 'progress') onProgress(payload);
        if (event === 'error') throw new Error(payload.message || '分析失败，请稍后重试');
        if (event === 'done') return payload as AnalysisResult;
      }
      if (done) throw new Error('连接已中断，报告可能仍在处理中。请刷新会话历史查看结果。');
    }
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
