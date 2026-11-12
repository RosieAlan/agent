export class RequestError extends Error {
  constructor(message: string, public status = 0) { super(message) }
}

// 全部页面共用：同源/api、JSON校验、后端错误映射、等待超时清理。
export async function request<T>(path: string, options: { method?: string; json?: unknown } = {}): Promise<T> {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), 100_000)
  try {
    const response = await fetch(`/api${path}`, {
      method: options.method ?? 'GET', signal: controller.signal,
      headers: options.json === undefined ? {} : { 'Content-Type': 'application/json' },
      body: options.json === undefined ? undefined : JSON.stringify(options.json),
    })
    if (!response.headers.get('content-type')?.includes('application/json')) {
      throw new RequestError('服务返回异常，请检查后端连接后重试', response.status)
    }
    const data = await response.json()
    if (!response.ok) {
      const detail = data?.detail
      const message = typeof detail === 'string' ? detail : Array.isArray(detail)
        ? detail.map((issue: { loc?: (string | number)[]; msg?: string }) => `${issue.loc?.slice(1).join('.') ?? '输入'}：${issue.msg ?? '请检查内容'}`).join('；')
        : '服务暂时无法完成请求，请稍后重试'
      throw new RequestError(message, response.status)
    }
    return data as T
  } catch (error) {
    if (controller.signal.aborted) throw new RequestError('等待超时，后台可能仍在处理。草案提交请保留原内容重试。')
    if (error instanceof RequestError) throw error
    throw new RequestError('无法连接服务，请检查后端8030与前端代理')
  } finally {
    window.clearTimeout(timer)
  }
}
