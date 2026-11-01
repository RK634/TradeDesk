import { apiGet, apiPost } from '@/features/auth/api'

export interface ArchiveRecord {
  record_id: string
  record_type: 'import_order' | 'export_order'
  reference: string
  status: string
  partner_name: string
  currency: string
  archived_at: string | null
  archived_by_user_id: string | null
  archive_reason: string | null
  created_at: string
}

export interface ArchivePage {
  items: ArchiveRecord[]
  total: number
  page: number
  page_size: number
}

export interface ArchiveEvent {
  id: string
  record_type: string
  record_id: string
  record_reference: string
  action: 'archived' | 'restored'
  reason: string
  actor_user_id: string | null
  created_at: string
}

function query(values: Record<string, string | undefined>) {
  const params = new URLSearchParams()
  Object.entries(values).forEach(([key, value]) => { if (value) params.set(key, value) })
  return params.toString()
}

export function getArchive(organizationId: string, search = '', recordType = '', startDate = '', endDate = '') {
  return apiGet<ArchivePage>(`/archive?${query({ organization_id: organizationId, search, record_type: recordType, start_date: startDate, end_date: endDate })}`)
}

export function getArchiveEligible(organizationId: string, search = '', recordType = '') {
  return apiGet<ArchivePage>(`/archive/eligible?${query({ organization_id: organizationId, search, record_type: recordType })}`)
}

export function getArchiveHistory(organizationId: string, recordType: string, recordId: string) {
  return apiGet<ArchiveEvent[]>(`/archive/${recordType}/${recordId}/history?${query({ organization_id: organizationId })}`)
}

export function archiveRecord(organizationId: string, record: ArchiveRecord, reason: string) {
  return apiPost<ArchiveRecord>(`/archive/${record.record_type}/${record.record_id}?${query({ organization_id: organizationId })}`, { reason })
}

export function restoreRecord(organizationId: string, record: ArchiveRecord, reason: string) {
  return apiPost<ArchiveRecord>(`/archive/${record.record_type}/${record.record_id}/restore?${query({ organization_id: organizationId })}`, { reason })
}
