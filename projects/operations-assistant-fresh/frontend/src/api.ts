export type Kind = 'inventory_check' | 'daily_report'
export interface Inventory { store_code: string; store_name: string; sku: string; product_name: string; available: number; reserved: number; inbound: number; is_low_stock: boolean; gap_to_threshold: number }
export interface Run { id: string; kind: Kind; status: 'queued' | 'running' | 'completed' | 'failed'; created_at: string; started_at: string | null; finished_at: string | null; attempts: number; error: string | null; result: { summary?: string; items?: Inventory[]; low_stock_count?: number; total_items?: number; report_date?: string; data_source?: string } | null }
export interface Todo { id: string; store_code: string; sku: string; title: string; status: 'open' | 'done'; available: number; threshold: number; updated_at: string }
export interface Notification { id: string; title: string; body: string; is_read: boolean; created_at: string }
export interface Schedule { kind: Kind; enabled: boolean; daily_time: string; threshold: number; next_run_at: string | null }
export interface Overview { data_source: string; counts: { low_stock: number; open_todos: number; unread_notifications: number }; worker: { healthy: boolean; last_seen: string | null }; latest_run: Run | null }

const controllers = new Set<AbortController>()
export function cancelRequests() { controllers.forEach(controller => controller.abort()); controllers.clear() }

// 所有业务请求走同源代理；超时中止连接，错误由页面统一展示。
export async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const controller = new AbortController()
  controllers.add(controller)
  const timeout = window.setTimeout(() => controller.abort(), 15000)
  try {
    const response = await fetch(`/api${path}`, {
      method, signal: controller.signal,
      headers: { Accept: 'application/json', ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
    if (!response.headers.get('content-type')?.includes('application/json')) throw new Error(`服务返回格式异常（HTTP ${response.status}），请检查后端与代理。`)
    const payload = await response.json()
    if (!response.ok) {
      const detail = payload.detail
      throw new Error(typeof detail === 'string' ? detail : `请求失败（HTTP ${response.status}），请核对输入后重试。`)
    }
    return payload as T
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw new Error('请求已超时或取消。请刷新状态；任务提交可使用原请求编号重试。')
    if (error instanceof TypeError) throw new Error('连接服务失败，请检查后端是否启动后重试。')
    throw error
  } finally { window.clearTimeout(timeout); controllers.delete(controller) }
}
