import { apiDelete, apiGet, apiPatch, apiPost, apiUpload } from '@/features/auth/api'
import type { GoodsReceipt, ImportDocument, ImportOrder, ImportOrderLine, ImportShipment, Page, ShipmentMilestone } from './types'

function organizationQuery(organizationId: string) { return new URLSearchParams({ organization_id: organizationId }).toString() }
export function listImportOrders(organizationId: string, search = '', statusFilter = 'all') {
  const query = new URLSearchParams({ organization_id: organizationId, page: '1', page_size: '100' })
  if (search.trim()) query.set('search', search.trim())
  if (statusFilter !== 'all') query.set('status', statusFilter)
  return apiGet<Page<ImportOrder>>(`/imports?${query.toString()}`)
}
export function createImportOrder(organizationId: string, payload: Record<string, unknown>) { return apiPost<ImportOrder>(`/imports?${organizationQuery(organizationId)}`, payload) }
export function updateImportOrder(organizationId: string, orderId: string, payload: Record<string, unknown>) { return apiPatch<ImportOrder>(`/imports/${orderId}?${organizationQuery(organizationId)}`, payload) }
export function submitImportOrder(organizationId: string, orderId: string) { return apiPost<ImportOrder>(`/imports/${orderId}/submit?${organizationQuery(organizationId)}`, {}) }
export function approveImportOrder(organizationId: string, orderId: string) { return apiPost<ImportOrder>(`/imports/${orderId}/approve?${organizationQuery(organizationId)}`, {}) }
export function rejectImportOrder(organizationId: string, orderId: string, reason: string) { return apiPost<ImportOrder>(`/imports/${orderId}/reject?${organizationQuery(organizationId)}`, { reason }) }
export function cancelImportOrder(organizationId: string, orderId: string) { return apiPost<ImportOrder>(`/imports/${orderId}/cancel?${organizationQuery(organizationId)}`, {}) }
export function addImportOrderItem(organizationId: string, orderId: string, payload: Record<string, unknown>) { return apiPost<ImportOrderLine>(`/imports/${orderId}/items?${organizationQuery(organizationId)}`, payload) }
export function updateImportCosts(organizationId: string, orderId: string, payload: Record<string, string | number>) { return apiPatch<ImportOrder>(`/imports/${orderId}/costs?${organizationQuery(organizationId)}`, payload) }
export function listImportShipments(organizationId: string, orderId: string) { return apiGet<ImportShipment[]>(`/imports/${orderId}/shipments?${organizationQuery(organizationId)}`) }
export function createImportShipment(organizationId: string, orderId: string, payload: Record<string, unknown>) { return apiPost<ImportShipment>(`/imports/${orderId}/shipments?${organizationQuery(organizationId)}`, payload) }
export function updateImportShipment(organizationId: string, shipmentId: string, payload: Record<string, unknown>) { return apiPatch<ImportShipment>(`/imports/shipments/${shipmentId}?${organizationQuery(organizationId)}`, payload) }
export function listShipmentMilestones(organizationId: string, shipmentId: string) { return apiGet<ShipmentMilestone[]>(`/imports/shipments/${shipmentId}/milestones?${organizationQuery(organizationId)}`) }
export function createShipmentMilestone(organizationId: string, shipmentId: string, payload: Record<string, unknown>) { return apiPost<ShipmentMilestone>(`/imports/shipments/${shipmentId}/milestones?${organizationQuery(organizationId)}`, payload) }
export function listGoodsReceipts(organizationId: string, orderId: string) { return apiGet<GoodsReceipt[]>(`/imports/${orderId}/receipts?${organizationQuery(organizationId)}`) }
export function createGoodsReceipt(organizationId: string, orderId: string, payload: Record<string, unknown>) { return apiPost<GoodsReceipt>(`/imports/${orderId}/receipts?${organizationQuery(organizationId)}`, payload) }
export function listImportDocuments(organizationId: string, orderId: string) { return apiGet<ImportDocument[]>(`/imports/${orderId}/documents?${organizationQuery(organizationId)}`) }
export function uploadImportDocument(organizationId: string, orderId: string, payload: FormData) { return apiUpload<ImportDocument>(`/imports/${orderId}/documents?${organizationQuery(organizationId)}`, payload) }
export function updateImportDocument(organizationId: string, orderId: string, documentId: string, payload: Record<string, unknown>) { return apiPatch<ImportDocument>(`/imports/${orderId}/documents/${documentId}?${organizationQuery(organizationId)}`, payload) }
export function deleteImportDocument(organizationId: string, orderId: string, documentId: string) { return apiDelete<void>(`/imports/${orderId}/documents/${documentId}?${organizationQuery(organizationId)}`) }
export function importDocumentDownloadPath(organizationId: string, orderId: string, documentId: string) { return `/imports/${orderId}/documents/${documentId}/download?${organizationQuery(organizationId)}` }
