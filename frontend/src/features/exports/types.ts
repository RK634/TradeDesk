export type ExportStatus = 'draft' | 'submitted' | 'approved' | 'rejected' | 'partially_dispatched' | 'dispatched' | 'partially_delivered' | 'delivered' | 'cancelled'
export type TransportMode = 'sea' | 'air' | 'road' | 'rail' | 'courier' | 'other'

export interface Page<T> { items: T[]; total: number; page: number; page_size: number }
export interface ExportOrderLine {
  id: string; organization_id: string; order_id: string; line_number: number; product_id: string
  product_sku_snapshot: string; product_name_snapshot: string; description: string | null
  quantity_ordered: string | number; quantity_reserved: string | number; quantity_dispatched: string | number
  quantity_delivered: string | number; quantity_not_dispatched: string | number; quantity_not_delivered: string | number
  unit_price: string | number; line_total: string | number
}
export interface ExportShipmentLine {
  id: string; organization_id: string; shipment_id: string; order_id: string; order_item_id: string
  quantity_dispatched: string | number; quantity_delivered: string | number; quantity_remaining: string | number
}
export interface ExportShipment {
  id: string; organization_id: string; order_id: string; shipment_reference: string; carrier: string | null
  tracking_reference: string | null; transport_mode: TransportMode; origin: string | null; destination: string | null
  status: 'in_transit' | 'delayed' | 'delivered'; estimated_departure: string | null; actual_departure: string
  estimated_arrival: string | null; actual_arrival: string | null; notes: string | null; items: ExportShipmentLine[]
}
export interface ExportDeliveryLine { id: string; shipment_item_id: string; quantity_delivered: string | number }
export interface ExportDelivery {
  id: string; order_id: string; shipment_id: string; delivery_reference: string; delivered_at: string
  notes: string | null; items: ExportDeliveryLine[]
}
export interface ExportStatusHistory { id: string; from_status: string | null; to_status: string; reason: string | null; actor_user_id: string; created_at: string }
export interface ExportOrder {
  id: string; organization_id: string; reference: string; customer_id: string; customer_name: string
  inventory_location_id: string; inventory_location_name: string; status: ExportStatus; currency: string
  destination_country: string | null; delivery_address: string | null; shipping_terms: string | null
  payment_terms_days: number; requested_ship_date: string | null; requested_delivery_date: string | null; notes: string | null
  goods_total: string | number; quantity_ordered: string | number; quantity_reserved: string | number
  quantity_dispatched: string | number; quantity_delivered: string | number; rejection_reason: string | null
  items: ExportOrderLine[]; shipments: ExportShipment[]; status_history: ExportStatusHistory[]; created_at: string; updated_at: string
}
