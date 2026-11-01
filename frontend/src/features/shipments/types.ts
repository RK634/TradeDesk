export type ShipmentType = 'import' | 'export'
export type ShipmentStatus = 'planned' | 'in_transit' | 'arrived' | 'delayed' | 'delivered' | 'cancelled'
export interface Shipment {
  id: string
  organization_id: string
  shipment_type: ShipmentType
  order_id: string
  order_reference: string
  shipment_reference: string
  carrier: string | null
  tracking_reference: string | null
  transport_mode: string
  origin: string | null
  destination: string | null
  estimated_departure: string | null
  actual_departure: string | null
  estimated_arrival: string | null
  actual_arrival: string | null
  status: ShipmentStatus
  delay_reason: string | null
  notes: string | null
  created_at: string
  updated_at: string | null
}
export interface ShipmentMilestone {
  id: string
  organization_id: string
  order_id: string
  shipment_id: string
  name: string
  description: string | null
  occurred_at: string
  created_by_user_id: string
  created_at: string
}
