import { apiGet, apiPatch, apiPost, apiPut } from '@/features/auth/api'
import type { ApprovalRecord, ApprovalRule, AutomationLog, NotificationPage, NotificationPreference, TaskRecord, Page } from './types'

function orgQuery(organizationId: string) { return new URLSearchParams({ organization_id: organizationId }).toString() }

export function listTasks(organizationId: string, status = 'all', assignedToMe = false) {
  const query = new URLSearchParams({ organization_id: organizationId, page: '1', page_size: '100' })
  if (status !== 'all') query.set('status', status)
  if (assignedToMe) query.set('assigned_to_me', 'true')
  return apiGet<Page<TaskRecord>>(`/tasks?${query.toString()}`)
}
export function getTask(organizationId: string, taskId: string) { return apiGet<TaskRecord>(`/tasks/${taskId}?${orgQuery(organizationId)}`) }
export function createTask(organizationId: string, payload: Record<string, unknown>) { return apiPost<TaskRecord>(`/tasks?${orgQuery(organizationId)}`, payload) }
export function updateTask(organizationId: string, taskId: string, payload: Record<string, unknown>) { return apiPatch<TaskRecord>(`/tasks/${taskId}?${orgQuery(organizationId)}`, payload) }
export function updateTaskStatus(organizationId: string, taskId: string, status: string, note?: string) { return apiPost<TaskRecord>(`/tasks/${taskId}/status?${orgQuery(organizationId)}`, { status, note }) }
export function addTaskComment(organizationId: string, taskId: string, body: string) { return apiPost(`/tasks/${taskId}/comments?${orgQuery(organizationId)}`, { body }) }

export function listApprovals(organizationId: string, status = 'all') {
  const query = new URLSearchParams({ organization_id: organizationId })
  if (status !== 'all') query.set('status', status)
  return apiGet<ApprovalRecord[]>(`/approvals?${query.toString()}`)
}
export function listApprovalRules(organizationId: string) { return apiGet<ApprovalRule[]>(`/approval-rules?${orgQuery(organizationId)}`) }
export function updateApprovalRule(organizationId: string, action: string, payload: Record<string, unknown>) { return apiPut<ApprovalRule>(`/approval-rules/${action}?${orgQuery(organizationId)}`, payload) }
export function decideApproval(organizationId: string, approvalId: string, status: string, decisionNote?: string) { return apiPost<ApprovalRecord>(`/approvals/${approvalId}/decision?${orgQuery(organizationId)}`, { status, decision_note: decisionNote }) }
export function cancelApproval(organizationId: string, approvalId: string, reason: string) { return apiPost<ApprovalRecord>(`/approvals/${approvalId}/cancel?${orgQuery(organizationId)}`, { reason }) }

export function listNotifications(organizationId: string, unreadOnly = false) {
  const query = new URLSearchParams({ organization_id: organizationId, page: '1', page_size: '100', unread_only: String(unreadOnly) })
  return apiGet<NotificationPage>(`/notifications?${query.toString()}`)
}
export function getUnreadCount(organizationId: string) { return apiGet<{ unread_count: number }>(`/notifications/unread-count?${orgQuery(organizationId)}`) }
export function markNotificationRead(organizationId: string, notificationId: string) { return apiPatch(`/notifications/${notificationId}/read?${orgQuery(organizationId)}`, {}) }
export function markAllNotificationsRead(organizationId: string) { return apiPost<{ updated_count: number }>(`/notifications/read-all?${orgQuery(organizationId)}`, {}) }
export function getNotificationPreferences(organizationId: string) { return apiGet<NotificationPreference[]>(`/notifications/preferences?${orgQuery(organizationId)}`) }
export function updateNotificationPreference(organizationId: string, category: string, inAppEnabled: boolean) { return apiPut<NotificationPreference>(`/notifications/preferences?${orgQuery(organizationId)}`, { category, in_app_enabled: inAppEnabled }) }
export function listAutomationLogs(organizationId: string) { return apiGet<AutomationLog[]>(`/notifications/automation-logs?${orgQuery(organizationId)}`) }
export function runAutomationNow(organizationId: string) { return apiPost(`/notifications/automation/run?${orgQuery(organizationId)}`, {}) }
