import { apiGet, apiPatch, apiPost } from '@/features/auth/api'
import type { Shipment, ShipmentMilestone, ShipmentType } from './types'

function orgQuery(organizationId: string) { return new URLSearchParams({ organization_id: organizationId }).toString() }
export function listShipments(organizationId: string, shipmentType = 'all', status = 'all', search = '') {
  const query = new URLSearchParams({ organization_id: organizationId, limit: '500' })
  if (shipmentType !== 'all') query.set('shipment_type', shipmentType)
  if (status !== 'all') query.set('status', status)
  if (search.trim()) query.set('search', search.trim())
  return apiGet<Shipment[]>(`/shipments?${query.toString()}`)
}
export function updateShipment(organizationId: string, type: ShipmentType, shipmentId: string, payload: Record<string, unknown>) {
  return apiPatch<Shipment>(`/shipments/${type}/${shipmentId}?${orgQuery(organizationId)}`, payload)
}
export function listShipmentMilestones(organizationId: string, type: ShipmentType, shipmentId: string) {
  return apiGet<ShipmentMilestone[]>(`/shipments/${type}/${shipmentId}/milestones?${orgQuery(organizationId)}`)
}
export function createShipmentMilestone(organizationId: string, type: ShipmentType, shipmentId: string, payload: Record<string, unknown>) {
  return apiPost<ShipmentMilestone>(`/shipments/${type}/${shipmentId}/milestones?${orgQuery(organizationId)}`, payload)
}
