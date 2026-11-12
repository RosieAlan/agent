export interface Profile { profile_id: string; country: string | null; currency: string | null; timezone: string | null }
export interface Scope { profile_id: string; start_date: string; end_date: string; campaign_id?: string; attribution_window: number; limit: number }
export interface Metrics { roas: string | null; ctr_percent: string | null; cpc: string | null }
export interface ReportRow {
  campaign_id: string; current_campaign_name?: string | null; report_date?: string; reported_days?: number
  spend: string | null; attributed_sales: string | null; current_daily_budget?: string | null
  metrics?: Metrics
}
export interface TaskResult {
  profile?: Profile; items?: ReportRow[]; unknown_items?: ReportRow[]; answer?: string
  matched_count?: number; unknown_count?: number; target_roas?: string; has_more?: boolean
}
export interface TaskRun { id: string; action: string; status: string; result: TaskResult | null; error: string | null; duration_ms: number | null }
export interface Analysis {
  status: string; answer: string; execution_order: string[]; tasks: TaskRun[]
  plan: { status: string; question: string; tasks: { id: string; action: string; depends_on: string[] }[] }
  diagnosis: {
    status: string; revise_count: number; warnings: string[]; references: Record<string, string>
    draft: { findings: { summary: string; evidence_ids: string[]; possible_causes: string[]; next_checks: string[] }[] } | null
    review: { passed: boolean; issues: string[] } | null
  } | null
}
export interface Proposal {
  id: string; profile_id: string; campaign_id: string; currency: string; source_budget: string
  proposed_budget: string; reason: string; status: 'pending_approval' | 'approved' | 'rejected'
  version: number; reviewer: string | null; created_at: string; updated_at: string; execution_status: string
}
export interface ProposalEvent { id: string; event_type: string; version: number; actor: string | null; created_at: string }
export interface DraftContext { profile_id: string; campaign_id: string; name?: string; budget?: string | null }

export const statusName: Record<string, string> = {
  completed: '已完成', needs_attention: '需要处理', clarification_required: '需要补充信息', ready: '计划就绪',
  pending: '等待执行', running: '执行中', failed: '失败', blocked: '前置任务未完成',
  passed: '评审通过', needs_review: '需要人工核对', unavailable: 'AI诊断暂不可用', skipped: '本轮无需诊断',
  pending_approval: '待审批', approved: '已批准', rejected: '已拒绝', created: '已创建',
}
export const taskName: Record<string, string> = { query_reports: '查询报表', find_low_roas: '汇总与筛选', write_review: '整理复盘' }
