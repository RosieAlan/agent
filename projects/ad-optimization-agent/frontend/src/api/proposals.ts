import { request } from './client'
import type { Proposal, ProposalEvent } from './types'

export const getProposals = () => request<Proposal[]>('/proposals?limit=50')
export const getProposal = (id: string) => request<Proposal>(`/proposals/detail?proposal_id=${encodeURIComponent(id)}`)
export const getEvents = (id: string) => request<ProposalEvent[]>(`/proposals/events?proposal_id=${encodeURIComponent(id)}`)
export const createProposal = (body: { idempotency_key: string; profile_id: string; campaign_id: string; proposed_budget: string; reason: string }) => request<Proposal>('/proposals', { method: 'POST', json: body })
export const decideProposal = (body: { proposal_id: string; expected_version: number; decision: 'approve' | 'reject'; reviewer: string }) => request<Proposal>('/proposals/decision', { method: 'POST', json: body })
