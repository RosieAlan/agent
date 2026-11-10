<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { api, cancelRequests, type Inventory, type Kind, type Notification, type Overview, type Run, type Schedule, type Todo } from './api'

const tabs = [{ id: 'inventory', title: '库存与巡检', icon: '▦' }, { id: 'reports', title: '日报与任务', icon: '▤' }, { id: 'todos', title: '运营待办', icon: '☑' }, { id: 'inbox', title: '通知收件箱', icon: '◷' }, { id: 'knowledge', title: 'SOP 知识库', icon: '▧' }]
const active = ref('inventory')
const overview = ref<Overview | null>(null)
const inventory = ref<Inventory[]>([])
const runs = ref<Run[]>([])
const todos = ref<Todo[]>([])
const notifications = ref<Notification[]>([])
const schedules = ref<Schedule[]>([])
const selectedRun = ref<Run | null>(null)
const sku = ref('')
const threshold = ref(20)
const appliedThreshold = ref(20)
const error = ref('')
const notice = ref('')
const refreshing = ref(false)
const searching = ref(false)
const busy = ref<Record<string, boolean>>({})
const requestKeys = ref<Partial<Record<Kind, { key: string; threshold: number }>>>({})
const lastRefresh = ref<string | null>(null)
let timer: number | undefined
let alive = true
const title = computed(() => tabs.find(tab => tab.id === active.value)?.title)
const openTodos = computed(() => todos.value.filter(todo => todo.status === 'open').length)
const pending = computed(() => runs.value.some(run => ['queued', 'running'].includes(run.status)))
const labels: Record<string, string> = { inventory_check: '库存巡检', daily_report: '运营日报', queued: '排队中', running: '执行中', completed: '已完成', failed: '执行失败' }
function date(value: string | null | undefined) { return value ? new Date(value).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false }) : '—' }
function message(err: unknown) { return err instanceof Error ? err.message : '操作失败，请重试。' }
function validThreshold() { if (!Number.isInteger(threshold.value) || threshold.value < 1 || threshold.value > 100000) throw new Error('预警阈值请填写 1–100000 的整数。') }
async function loadInventory() {
  if (searching.value) return
  searching.value = true; error.value = ''
  try {
    validThreshold()
    const params = new URLSearchParams({ threshold: String(threshold.value) })
    if (sku.value.trim()) params.set('sku', sku.value.trim())
    const data = await api<{ items: Inventory[]; threshold: number }>(`/operations/inventory?${params}`)
    inventory.value = data.items; appliedThreshold.value = data.threshold
  } catch (err) { error.value = message(err) } finally { searching.value = false }
}
// 轮询采用单次在途保护；任一路失败保留上次已取得的数据并标注更新时间。
async function refresh() {
  if (refreshing.value) return
  refreshing.value = true
  const results = await Promise.allSettled([
    api<Overview>('/operations/overview').then(data => { overview.value = data }),
    api<Run[]>('/operations/runs?limit=30').then(data => { runs.value = data; if (selectedRun.value) selectedRun.value = data.find(run => run.id === selectedRun.value?.id) ?? selectedRun.value }),
    api<Todo[]>('/operations/todos').then(data => { todos.value = data }),
    api<Notification[]>('/operations/notifications').then(data => { notifications.value = data }),
  ])
  if (!alive) return
  const failed = results.find(result => result.status === 'rejected')
  if (failed?.status === 'rejected') error.value = message(failed.reason)
  else { lastRefresh.value = new Date().toISOString(); error.value = '' }
  refreshing.value = false
}
async function action(key: string, task: () => Promise<void>) {
  if (busy.value[key]) return
  busy.value[key] = true; error.value = ''; notice.value = ''
  try { await task() } catch (err) { error.value = message(err) } finally { busy.value[key] = false }
}
async function enqueue(kind: Kind) {
  await action(kind, async () => {
    validThreshold()
    // 连接超时后保留相同编号与参数，服务端幂等处理可避免重复任务。
    const request = requestKeys.value[kind] ?? { key: crypto.randomUUID(), threshold: threshold.value }
    requestKeys.value[kind] = request
    const run = await api<Run>('/operations/runs', 'POST', { kind, threshold: request.threshold, idempotency_key: request.key })
    delete requestKeys.value[kind]
    selectedRun.value = run; active.value = 'reports'; notice.value = `${labels[kind]}已提交，后台将继续执行。`
    await refresh()
  })
}
async function loadSchedules() {
  try { schedules.value = await api<Schedule[]>('/operations/schedules') } catch (err) { error.value = message(err) }
}
async function saveSchedule(schedule: Schedule) {
  await action(`schedule-${schedule.kind}`, async () => {
    const saved = await api<Schedule>(`/operations/schedules/${schedule.kind}`, 'PUT', { enabled: schedule.enabled, daily_time: schedule.daily_time, threshold: schedule.threshold })
    schedules.value = schedules.value.map(row => row.kind === saved.kind ? saved : row)
    notice.value = `${labels[saved.kind]}定时设置已保存。`
  })
}
async function toggleTodo(todo: Todo) {
  await action(`todo-${todo.id}`, async () => {
    const saved = await api<Todo>(`/operations/todos/${todo.id}`, 'PATCH', { status: todo.status === 'open' ? 'done' : 'open' })
    todos.value = todos.value.map(row => row.id === saved.id ? saved : row)
    await refresh()
  })
}
async function readNotification(item: Notification) {
  await action(`notification-${item.id}`, async () => {
    const saved = await api<Notification>(`/operations/notifications/${item.id}`, 'PATCH', { is_read: true })
    notifications.value = notifications.value.map(row => row.id === saved.id ? saved : row)
    await refresh()
  })
}
async function showRun(run: Run) {
  await action('detail', async () => { selectedRun.value = await api<Run>(`/operations/runs/${run.id}`) })
}
onMounted(async () => {
  await Promise.all([refresh(), loadInventory(), loadSchedules()])
  if (alive) timer = window.setInterval(() => { void refresh() }, 5000)
})
onUnmounted(() => { alive = false; window.clearInterval(timer); cancelRequests() })
</script>

<template>
  <div class="workbench">
    <a class="skip" href="#main">跳至工作区</a>
    <aside class="sidebar">
      <a class="brand" href="#" @click.prevent="active = 'inventory'"><span class="brand-mark">运</span><span>运营提效助手<small>日常运营工作台</small></span></a>
      <nav aria-label="主导航"><button v-for="tab in tabs" :key="tab.id" :class="{ active: active === tab.id }" :aria-current="active === tab.id ? 'page' : undefined" @click="active = tab.id"><span aria-hidden="true">{{ tab.icon }}</span>{{ tab.title }}<b v-if="tab.id === 'todos' && openTodos">{{ openTodos }}</b></button></nav>
      <div class="sidebar-foot"><span class="source-dot"></span>合成数据演示环境<small>业务数据由本地服务提供<br>时间统一为北京时间</small></div>
    </aside>
    <div class="workspace">
      <header class="topbar"><span>运营工作台 <span class="separator">/</span> {{ title }}</span><span class="environment">本地演练</span></header>
      <main id="main">
        <div class="page-heading"><div><h1>{{ title }}</h1><p>{{ active === 'inventory' ? '检查可用库存，及时安排补货与跟进。' : active === 'reports' ? '提交后台任务，查看执行记录与每日运营结果。' : active === 'todos' ? '跟进巡检产生的库存风险，完成处理后更新状态。' : active === 'inbox' ? '集中查看任务结果和运营提醒。' : '查阅运营规范，上传文档并提问。' }}</p></div><button class="quiet" :disabled="refreshing" @click="refresh">{{ refreshing ? '刷新中…' : '刷新状态' }}</button></div>
        <div v-if="error" class="feedback error" role="alert"><strong>操作需要处理</strong><span>{{ error }}</span><button @click="error = ''" aria-label="关闭错误提示">×</button></div>
        <div v-if="notice" class="feedback success" role="status">{{ notice }}<button @click="notice = ''" aria-label="关闭成功提示">×</button></div>
        <div class="health-line"><span :class="['health-dot', { healthy: overview?.worker.healthy }]"></span><span>{{ overview ? (overview.worker.healthy ? '后台执行器在线' : '后台执行器心跳异常，请检查 Worker 服务') : '正在连接后台服务' }}</span><span v-if="overview && !overview.worker.healthy">最近心跳 {{ date(overview.worker.last_seen) }}</span><span class="updated">更新于 {{ date(lastRefresh) }} <span v-if="pending">· 任务每 5 秒同步</span></span></div>

        <template v-if="active === 'inventory'">
          <section class="summary" aria-label="运营概览"><div><span>低库存记录</span><strong>{{ overview?.counts.low_stock ?? '—' }}<small>条</small></strong><p>默认预警口径由后台统计</p></div><div><span>待处理事项</span><strong>{{ overview?.counts.open_todos ?? '—' }}<small>项</small></strong><button class="text-button" @click="active = 'todos'">进入运营待办</button></div><div><span>未读通知</span><strong>{{ overview?.counts.unread_notifications ?? '—' }}<small>条</small></strong><button class="text-button" @click="active = 'inbox'">查看通知收件箱</button></div></section>
          <section class="panel"><div class="panel-title"><div><h2>库存明细</h2><p>可用库存低于阈值时触发预警；在途数量单独展示。</p></div><span class="pill">合成演示数据</span></div><form class="filter" @submit.prevent="loadInventory"><label>商品 SKU<input v-model="sku" placeholder="全部 SKU" maxlength="100"></label><label class="number-field">预警阈值<input v-model.number="threshold" type="number" min="1" max="100000" step="1" required></label><button :disabled="searching" type="submit">{{ searching ? '查询中…' : '查询库存' }}</button><button type="button" class="quiet" :disabled="busy.inventory_check" @click="enqueue('inventory_check')">{{ busy.inventory_check ? '提交中…' : requestKeys.inventory_check ? '重试原巡检请求' : '运行库存巡检' }}</button></form><p v-if="requestKeys.inventory_check" class="inline-note">原巡检请求使用阈值 {{ requestKeys.inventory_check.threshold }}，重试沿用原编号。</p><div class="table-scroll"><table><caption class="sr-only">库存明细，当前预警阈值 {{ appliedThreshold }}</caption><thead><tr><th>商品 / SKU</th><th>店铺</th><th class="numeric">可用</th><th class="numeric">预留</th><th class="numeric">在途</th><th class="numeric">缺口</th><th>库存状态</th></tr></thead><tbody><tr v-for="item in inventory" :key="`${item.store_code}-${item.sku}`"><td><strong>{{ item.product_name }}</strong><small>{{ item.sku }}</small></td><td>{{ item.store_name }}<small>{{ item.store_code }}</small></td><td class="numeric" :class="{ 'risk-number': item.is_low_stock }">{{ item.available }}</td><td class="numeric">{{ item.reserved }}</td><td class="numeric">{{ item.inbound }}</td><td class="numeric">{{ item.gap_to_threshold }}</td><td><span :class="['status', item.is_low_stock ? 'warning' : 'completed']">{{ item.is_low_stock ? '待补货' : '充足' }}</span></td></tr><tr v-if="!inventory.length"><td colspan="7" class="empty">{{ searching ? '正在读取库存…' : '当前查询暂无记录，请核对 SKU 或刷新查询。' }}</td></tr></tbody></table></div><div class="table-footer">{{ inventory.length }} 条记录 <span>当前查询阈值 {{ appliedThreshold }}</span></div></section>
        </template>

        <template v-if="active === 'reports'">
          <section class="panel"><div class="panel-title"><div><h2>运行任务</h2><p>提交后由后台执行器处理，页面持续同步执行状态。</p></div></div><div class="task-actions"><label class="number-field">本次预警阈值<input v-model.number="threshold" type="number" min="1" max="100000" required></label><button :disabled="busy.daily_report" @click="enqueue('daily_report')">{{ busy.daily_report ? '提交中…' : requestKeys.daily_report ? '重试原日报请求' : '生成运营日报' }}</button><button class="quiet" :disabled="busy.inventory_check" @click="enqueue('inventory_check')">{{ busy.inventory_check ? '提交中…' : requestKeys.inventory_check ? '重试原巡检请求' : '运行库存巡检' }}</button></div><p v-for="(request, kind) in requestKeys" :key="kind" class="inline-note">{{ labels[kind] }}请求待确认，阈值 {{ request?.threshold }}；重试会沿用原请求编号。</p></section>
          <section class="panel"><div class="panel-title"><div><h2>执行记录</h2><p>保留最近 30 次任务，可查看报告正文及失败原因。</p></div></div><div class="table-scroll"><table><thead><tr><th>任务</th><th>提交时间</th><th>状态</th><th class="numeric">尝试次数</th><th>操作</th></tr></thead><tbody><tr v-for="run in runs" :key="run.id"><td><strong>{{ labels[run.kind] }}</strong><small class="run-id">{{ run.id }}</small></td><td>{{ date(run.created_at) }}</td><td><span :class="['status', run.status]">{{ labels[run.status] }}</span></td><td class="numeric">{{ run.attempts }}</td><td><button class="text-button" :disabled="busy.detail" @click="showRun(run)">查看详情</button></td></tr><tr v-if="!runs.length"><td colspan="5" class="empty">提交一次巡检或日报后，这里显示执行记录。</td></tr></tbody></table></div></section>
          <section v-if="selectedRun" class="panel run-detail" aria-live="polite"><div class="panel-title"><div><h2>{{ labels[selectedRun.kind] }}详情</h2><p>{{ selectedRun.id }}</p></div><button class="quiet" @click="selectedRun = null">收起详情</button></div><dl class="details"><div><dt>状态</dt><dd>{{ labels[selectedRun.status] }}</dd></div><div><dt>开始时间</dt><dd>{{ date(selectedRun.started_at) }}</dd></div><div><dt>完成时间</dt><dd>{{ date(selectedRun.finished_at) }}</dd></div></dl><p v-if="selectedRun.error" class="failure-text">{{ selectedRun.error }}</p><template v-if="selectedRun.result"><p class="report-text">{{ selectedRun.result.summary }}</p><div class="report-metrics"><span>报告日期 {{ selectedRun.result.report_date ?? '—' }}</span><span>库存记录 {{ selectedRun.result.total_items ?? '—' }}</span><span>低库存 {{ selectedRun.result.low_stock_count ?? '—' }}</span><span>数据来源：合成演示</span></div><div v-if="selectedRun.result.items?.length" class="table-scroll"><table><thead><tr><th>SKU</th><th>店铺</th><th class="numeric">可用库存</th></tr></thead><tbody><tr v-for="(item, index) in selectedRun.result.items" :key="index"><td>{{ item.sku }}</td><td>{{ item.store_name || item.store_code }}</td><td class="numeric">{{ item.available }}</td></tr></tbody></table></div></template><p v-else-if="selectedRun.status === 'queued' || selectedRun.status === 'running'" class="inline-note">后台正在处理。执行器离线时，任务将在恢复后继续处理。</p></section>
          <section class="panel"><div class="panel-title"><div><h2>每日定时任务</h2><p>时区：Asia/Shanghai（北京时间）。保存后由后台调度执行。</p></div><button class="quiet" @click="loadSchedules">重新读取</button></div><form v-for="schedule in schedules" :key="schedule.kind" class="schedule-row" @submit.prevent="saveSchedule(schedule)"><strong>{{ labels[schedule.kind] }}</strong><label class="check-label"><input v-model="schedule.enabled" type="checkbox">启用</label><label>每天执行时间<input v-model="schedule.daily_time" type="time" required></label><label class="number-field">预警阈值<input v-model.number="schedule.threshold" type="number" min="1" max="100000" required></label><button :disabled="busy[`schedule-${schedule.kind}`]">{{ busy[`schedule-${schedule.kind}`] ? '保存中…' : '保存设置' }}</button><small>下次执行 {{ date(schedule.next_run_at) }}</small></form><p v-if="!schedules.length" class="empty">定时设置尚未读取，请重新读取。</p></section>
        </template>

        <section v-if="active === 'todos'" class="panel"><div class="panel-title"><div><h2>补货跟进清单</h2><p>{{ openTodos }} 项待处理。处理完成后可标记完成，也可重新打开。</p></div></div><div class="table-scroll"><table><thead><tr><th>待办事项</th><th>店铺 / SKU</th><th>库存 / 阈值</th><th>状态</th><th>操作</th></tr></thead><tbody><tr v-for="todo in todos" :key="todo.id"><td><strong>{{ todo.title }}</strong><small>{{ date(todo.updated_at) }}</small></td><td>{{ todo.store_code }}<small>{{ todo.sku }}</small></td><td>{{ todo.available }} / {{ todo.threshold }}</td><td><span :class="['status', todo.status === 'done' ? 'completed' : 'warning']">{{ todo.status === 'done' ? '已完成' : '待处理' }}</span></td><td><button class="quiet" :disabled="busy[`todo-${todo.id}`]" @click="toggleTodo(todo)">{{ busy[`todo-${todo.id}`] ? '更新中…' : todo.status === 'open' ? '标记完成' : '重新打开' }}</button></td></tr><tr v-if="!todos.length"><td colspan="5" class="empty">当前暂无待办，运行库存巡检后可生成补货跟进事项。</td></tr></tbody></table></div></section>
        <section v-if="active === 'inbox'" class="panel"><div class="panel-title"><div><h2>任务与运营通知</h2><p>任务完成或失败后，后台会生成对应通知。</p></div></div><article v-for="item in notifications" :key="item.id" :class="['notification', { unread: !item.is_read }]"><div><h3>{{ item.title }}<span v-if="!item.is_read" class="unread-dot" aria-label="未读"></span></h3><p>{{ item.body }}</p><small>{{ date(item.created_at) }}</small></div><button v-if="!item.is_read" class="quiet" :disabled="busy[`notification-${item.id}`]" @click="readNotification(item)">{{ busy[`notification-${item.id}`] ? '更新中…' : '标记已读' }}</button><span v-else class="read-label">已读</span></article><p v-if="!notifications.length" class="empty">当前暂无通知，任务结果将在这里归档。</p></section>
        <section v-if="active === 'knowledge'" class="panel knowledge-panel"><div class="panel-title"><div><h2>运营 SOP 文档与问答</h2><p>复用现有知识库，文档与引用由后端管理。</p></div><a class="quiet link-button" href="/knowledge" target="_blank" rel="noopener">新窗口打开</a></div><iframe title="运营 SOP 知识库" src="/knowledge"></iframe></section>
        <footer class="page-footer">运营提效助手<span>合成演示数据 · 实际 API 读写 · 北京时间</span></footer>
      </main>
    </div>
  </div>
</template>

<style scoped>
:global(body){margin:0}
.workbench{--ink:#213b38;--muted:#657571;--line:#dce3df;--paper:#fff;--base:#f3f6f3;--teal:#17675d;--soft:#e6f0eb;display:flex;min-height:100vh;color:var(--ink);background:var(--base);font-family:"Microsoft YaHei","PingFang SC",sans-serif;font-size:14px;line-height:1.6}.workbench :deep(*){box-sizing:border-box}.workbench :deep(button),.workbench :deep(input){font:inherit}.workbench :deep(button),.link-button{border:1px solid var(--teal);border-radius:5px;background:var(--teal);color:white;padding:9px 16px;cursor:pointer;white-space:nowrap;text-decoration:none}.workbench :deep(button:hover:not(:disabled)){filter:brightness(.94)}.workbench :deep(button:disabled){opacity:.55;cursor:wait}.workbench :deep(button:focus-visible),.workbench :deep(a:focus-visible),.workbench :deep(input:focus-visible){outline:3px solid #76b6aa;outline-offset:3px}.workbench .quiet{background:white;color:var(--ink);border-color:#cdd7d0}.workbench .text-button{border:0;padding:0;background:transparent;color:var(--teal);text-align:left}.workbench :deep(input){border:1px solid #c5d1c9;border-radius:4px;background:white;color:var(--ink);padding:9px 10px;min-width:0;max-width:100%;height:42px}.workbench :deep(label){display:flex;flex-direction:column;gap:6px;font-size:12px;color:var(--muted)}.workbench :deep(h1),.workbench :deep(h2),.workbench :deep(h3),.workbench :deep(p){margin:0}.workbench :deep(h1){font-size:26px;font-weight:600;letter-spacing:.02em}.workbench :deep(h2){font-size:17px;font-weight:600}.workbench :deep(h3){font-size:15px;font-weight:600}.sidebar{width:218px;flex-shrink:0;background:#edf2ed;border-right:1px solid var(--line);padding:28px 18px;display:flex;flex-direction:column;position:fixed;inset:0 auto 0 0}.brand{display:flex;gap:10px;align-items:center;color:var(--ink);text-decoration:none;font-size:16px;font-weight:600}.brand-mark{display:flex;align-items:center;justify-content:center;width:37px;height:37px;background:var(--teal);color:white;border-radius:6px;font-size:19px}.brand small{display:block;color:var(--muted);font-size:11px;font-weight:400;margin-top:2px}.sidebar nav{display:flex;flex-direction:column;gap:7px;margin-top:43px}.sidebar nav button{display:flex;gap:12px;align-items:center;width:100%;padding:12px;border:0;color:#50645b;background:transparent;text-align:left}.sidebar nav button>span{font-size:20px;width:20px;line-height:1}.sidebar nav button.active{background:#d9e8df;color:#165c51;font-weight:600}.sidebar nav b{margin-left:auto;background:white;border-radius:4px;font-size:11px;padding:0 5px}.sidebar-foot{margin-top:auto;padding:20px 6px 0;font-size:12px;color:#49655a}.sidebar-foot small{display:block;color:var(--muted);font-size:11px;margin-top:8px;line-height:1.8}.source-dot,.health-dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:#ac7d29;margin-right:6px}.source-dot{background:#17675d}.workspace{margin-left:218px;width:calc(100% - 218px)}.topbar{height:64px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;padding:0 36px;color:#64746d;font-size:12px;background:#fafcf9}.separator{color:#a2b1a6;margin:0 12px}.environment{border:1px solid #cbd8ce;padding:3px 10px;border-radius:4px;font-size:11px}main{max-width:1450px;margin:auto;padding:30px 36px}.page-heading{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:20px}.page-heading p{color:var(--muted);font-size:13px;margin-top:5px}.health-line{display:flex;gap:6px;align-items:center;flex-wrap:wrap;color:var(--muted);font-size:11px;margin-bottom:23px}.health-dot{background:#b38132;margin:0}.health-dot.healthy{background:#398475}.updated{margin-left:auto;color:#7d8b83}.summary{display:grid;grid-template-columns:repeat(3,1fr);margin-bottom:26px;border-block:1px solid #d3dfd5;background:#eaf1e9}.summary>div{padding:21px 25px;position:relative}.summary>div+div{border-left:1px solid #d3dfd5}.summary>div>span{font-size:12px;color:#527063}.summary strong{display:block;font-size:35px;font-weight:500;line-height:1.5}.summary strong small{font-size:12px;color:var(--muted);margin-left:8px}.summary p,.summary button{font-size:11px;color:var(--muted)}.panel{background:var(--paper);border:1px solid var(--line);border-radius:7px;margin-bottom:22px;overflow:hidden}.panel-title{display:flex;justify-content:space-between;align-items:center;padding:21px 24px;gap:16px}.panel-title p{font-size:12px;color:var(--muted);margin-top:4px;overflow-wrap:anywhere}.pill{background:#eff4eb;color:#55704e;padding:4px 9px;font-size:11px;white-space:nowrap;border:1px solid #d9e4d2;border-radius:4px}.filter,.task-actions{display:flex;gap:12px;align-items:flex-end;padding:0 24px 22px;flex-wrap:wrap}.filter label:first-child{width:245px}.number-field{width:120px}.table-scroll{overflow:auto}table{width:100%;border-collapse:collapse;white-space:nowrap;font-size:12px}th{background:#f6f8f5;color:#78877b;font-size:11px;font-weight:500;text-align:left;padding:11px 23px;border-block:1px solid var(--line)}td{padding:16px 23px;border-bottom:1px solid #e9eeea}tr:last-child td{border-bottom:0}td strong{font-weight:500}td small{display:block;font-size:11px;color:#849086;margin-top:3px}.numeric{text-align:right;font-variant-numeric:tabular-nums}.risk-number{color:#a36b22;font-weight:600}.status{display:inline-block;border-radius:4px;font-size:11px;padding:3px 8px;background:#eef2ef;color:#6f7d72}.status.warning,.status.queued{background:#fbf2df;color:#926623}.status.completed{background:#e9f3ec;color:#3f795c}.status.running{background:#e5f0f5;color:#377491}.status.failed{background:#f8e9e6;color:#a64436}.table-footer{border-top:1px solid var(--line);padding:12px 24px;font-size:11px;color:var(--muted);display:flex;justify-content:space-between}.empty{padding:42px 24px!important;text-align:center;color:var(--muted);white-space:normal}.page-footer{display:flex;justify-content:space-between;font-size:11px;color:#8a968c;padding:5px 0 15px}.feedback{display:flex;align-items:center;gap:12px;border:1px solid;border-radius:5px;padding:12px 15px;margin-bottom:16px;font-size:12px}.feedback.error{background:#fff4ee;border-color:#edc7b5;color:#9b4a32}.feedback.success{background:#eaf5ef;border-color:#bcddcb;color:#2b6d4c}.feedback button{margin-left:auto;background:transparent;color:inherit;border:0;padding:0 5px;font-size:19px}.inline-note{font-size:12px;color:var(--muted);padding:0 24px 18px}.details{display:flex;gap:40px;margin:0;padding:0 24px 20px;flex-wrap:wrap}.details dt{color:var(--muted);font-size:11px}.details dd{margin:4px 0 0;font-size:12px}.report-text{white-space:pre-wrap;padding:20px 24px;border-top:1px solid var(--line);line-height:1.9}.report-metrics{display:flex;gap:20px;flex-wrap:wrap;font-size:11px;color:var(--muted);padding:0 24px 20px}.failure-text{margin:0 24px 20px!important;padding:12px;background:#fff0e9;color:#a44e35;font-size:12px;white-space:pre-wrap;overflow-wrap:anywhere}.run-id{max-width:180px;overflow:hidden;text-overflow:ellipsis}.schedule-row{display:flex;align-items:center;gap:18px;flex-wrap:wrap;padding:20px 24px;border-top:1px solid var(--line)}.schedule-row>strong{min-width:85px;font-size:13px;font-weight:500}.schedule-row .check-label{flex-direction:row;align-items:center;color:var(--ink);gap:6px}.check-label input{height:auto;accent-color:var(--teal)}.schedule-row small{font-size:11px;color:var(--muted);width:100%}.notification{padding:22px 24px;border-top:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;gap:20px}.notification.unread{background:#f8fbf6;border-left:3px solid #4f9273;padding-left:21px}.notification p{color:var(--muted);font-size:13px;margin:6px 0;white-space:pre-wrap}.notification small,.read-label{font-size:11px;color:#839086}.unread-dot{display:inline-block;width:6px;height:6px;background:var(--teal);border-radius:50%;margin-left:10px;vertical-align:middle}.knowledge-panel iframe{display:block;border:0;border-top:1px solid var(--line);width:100%;height:calc(100vh - 320px);min-height:620px;background:white}.link-button{font-size:12px}.sr-only,.skip{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}.skip:focus{position:fixed;width:auto;height:auto;clip-path:none;z-index:100;background:white;padding:10px;top:5px;left:5px}
@media(max-width:1100px){.sidebar{width:190px;padding:25px 13px}.workspace{margin-left:190px;width:calc(100% - 190px)}main{padding:25px 22px}.topbar{padding-inline:22px}.filter label:first-child{width:180px}th,td{padding-inline:17px}.summary>div{padding:18px}}
@media(max-width:760px){.workbench{display:block}.sidebar{position:static;width:100%;padding:16px 18px 0;border-right:0;border-bottom:1px solid var(--line)}.brand{font-size:15px}.brand-mark{width:32px;height:32px;font-size:16px}.brand small{display:none}.sidebar nav{flex-direction:row;margin-top:16px;overflow:auto;gap:4px;padding-bottom:9px}.sidebar nav button{padding:9px 12px;width:auto;font-size:12px;gap:6px}.sidebar nav button>span{display:none}.sidebar-foot{display:none}.workspace{margin-left:0;width:100%}.topbar{height:43px;padding:0 18px;font-size:11px}main{padding:22px 15px}.page-heading{align-items:flex-start}.page-heading h1{font-size:23px}.page-heading p{font-size:12px;max-width:240px}.page-heading>.quiet{font-size:11px;padding:7px 10px}.health-line{gap:5px}.updated{margin-left:0;width:100%;padding-left:12px}.summary{margin-bottom:20px}.summary>div{padding:15px 10px}.summary strong{font-size:29px}.summary p{font-size:10px}.summary .text-button{font-size:10px}.panel-title{padding:18px 16px;align-items:flex-start}.panel-title p{font-size:11px}.pill{font-size:10px;padding:3px 6px}.filter,.task-actions{padding:0 16px 18px;gap:10px}.filter label:first-child{flex:1;min-width:150px}.filter .number-field{width:100px}.filter>button{flex:1;padding-inline:10px}th,td{padding:12px 15px}.table-footer{padding:11px 15px}.page-footer{gap:8px;flex-wrap:wrap}.feedback{align-items:flex-start;gap:7px;flex-wrap:wrap}.feedback strong{width:100%}.feedback button{position:absolute;right:27px}.schedule-row{padding:18px 16px;gap:14px}.schedule-row>strong{min-width:75px}.schedule-row label{flex:1;min-width:90px}.schedule-row .check-label{flex:0;min-width:65px}.schedule-row button{align-self:flex-end}.notification{padding:18px 16px;align-items:flex-start}.notification.unread{padding-left:13px}.notification button{font-size:11px;padding:7px 10px}.details{gap:18px;padding-inline:16px}.report-text{padding:16px}.knowledge-panel iframe{min-height:650px}.panel-title .link-button{font-size:11px;padding:7px 8px}}
@media(prefers-reduced-motion:reduce){.workbench :deep(*){scroll-behavior:auto!important}}
</style>
