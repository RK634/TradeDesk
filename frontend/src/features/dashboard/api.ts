import { apiGet } from '@/features/auth/api'
import type { DashboardSummary } from './types'

export function getDashboardSummary(input: { organizationId: string; startDate: string; endDate: string }) {
  const query = new URLSearchParams({
    organization_id: input.organizationId,
    start_date: input.startDate,
    end_date: input.endDate,
  })
  return apiGet<DashboardSummary>(`/dashboard/summary?${query.toString()}`)
}
