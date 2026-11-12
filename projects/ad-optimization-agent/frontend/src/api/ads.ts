import { request } from './client'
import type { Analysis, Profile, Scope } from './types'

export const getProfiles = () => request<Profile[]>('/ads/profiles?limit=100')
export const analyze = (goal: string, scope: Scope) => request<Analysis>('/assistant/analyze', { method: 'POST', json: { goal, scope } })
