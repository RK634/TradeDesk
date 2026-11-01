import { apiGet, apiPost, apiPatch } from '@/features/auth/api'
import type { ExportDelivery, ExportOrder, ExportShipment, Page } from './types'

function orgQuery(organizationId: string) { return new URLSearchParams({ organization_id: organizationId }).toString() }
export function listExportOrders(organizationId: string, search = '', statusFilter = 'all') {
  const query = new URLSearchParams({ organization_id: organizationId, page: '1', page_size: '100' })
  if (search.trim()) query.set('search', search.trim())
  if (statusFilter !== 'all') query.set('status', statusFilter)
  return apiGet<Page<ExportOrder>>(`/exports?${query.toString()}`)
}
export function createExportOrder(organizationId: string, payload: Record<string, unknown>) {
  return apiPost<ExportOrder>(`/exports?${orgQuery(organizationId)}`, payload)
}
export function updateExportOrder(organizationId: string, orderId: string, payload: Record<string, unknown>) {
  return apiPatch<ExportOrder>(`/exports/${orderId}?${orgQuery(organizationId)}`, payload)
}
export function submitExportOrder(organizationId: string, orderId: string) {
  return apiPost<ExportOrder>(`/exports/${orderId}/submit?${orgQuery(organizationId)}`, {})
}
export function approveExportOrder(organizationId: string, orderId: string) {
  return apiPost<ExportOrder>(`/exports/${orderId}/approve?${orgQuery(organizationId)}`, {})
}
export function rejectExportOrder(organizationId: string, orderId: string, reason: string) {
  return apiPost<ExportOrder>(`/exports/${orderId}/reject?${orgQuery(organizationId)}`, { reason })
}
export function cancelExportOrder(organizationId: string, orderId: string) {
  return apiPost<ExportOrder>(`/exports/${orderId}/cancel?${orgQuery(organizationId)}`, {})
}
export function createExportShipment(organizationId: string, orderId: string, payload: Record<string, unknown>) {
  return apiPost<ExportShipment>(`/exports/${orderId}/shipments?${orgQuery(organizationId)}`, payload)
}
export function createExportDelivery(organizationId: string, orderId: string, shipmentId: string, payload: Record<string, unknown>) {
  return apiPost<ExportDelivery>(`/exports/${orderId}/shipments/${shipmentId}/deliveries?${orgQuery(organizationId)}`, payload)
}
export function listExportDeliveries(organizationId: string, orderId: string) {
  return apiGet<ExportDelivery[]>(`/exports/${orderId}/deliveries?${orgQuery(organizationId)}`)
}
