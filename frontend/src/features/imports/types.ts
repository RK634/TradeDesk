export type ImportStatus = 'draft' | 'submitted' | 'approved' | 'rejected' | 'partially_received' | 'received' | 'cancelled'
export type TransportMode = 'sea' | 'air' | 'road' | 'rail' | 'courier' | 'other'
export type ShipmentStatus = 'planned' | 'in_transit' | 'arrived' | 'delayed' | 'delivered' | 'cancelled'
export type DocumentVerificationStatus = 'pending' | 'verified' | 'rejected'

export interface Page<T> { items: T[]; total: number; page: number; page_size: number }
export interface ImportOrderLine {
  id: string; organization_id: string; order_id: string; line_number: number; product_id: string
  product_sku_snapshot: string; product_name_snapshot: string; description: string | null
  quantity_ordered: string | number; quantity_received: string | number; quantity_remaining: string | number
  unit_price: string | number; line_total: string | number; created_at: string; updated_at: string
}
export interface ImportStatusHistory { id: string; from_status: string | null; to_status: string; reason: string | null; actor_user_id: string; created_at: string }
export interface ImportOrder {
  id: string; organization_id: string; reference: string; supplier_id: string; supplier_name: string; status: ImportStatus
  currency: string; purchase_terms: string | null; country_of_origin: string | null; destination: string | null
  estimated_departure_date: string | null; estimated_arrival_date: string | null; actual_departure_date: string | null; actual_arrival_date: string | null
  estimated_freight_cost: string | number; estimated_insurance_cost: string | number; estimated_duties: string | number; estimated_other_costs: string | number
  estimated_goods_total: string | number; estimated_total_cost: string | number
  actual_freight_cost: string | number; actual_insurance_cost: string | number; actual_duties: string | number; actual_other_costs: string | number; actual_total_cost: string | number
  assigned_user_id: string | null; notes: string | null; created_by_user_id: string; submitted_at: string | null
  approved_by_user_id: string | null; approved_at: string | null; rejection_reason: string | null; created_at: string; updated_at: string
  items: ImportOrderLine[]; status_history: ImportStatusHistory[]
}
export interface ImportShipment {
  id: string; organization_id: string; order_id: string; shipment_reference: string; carrier: string | null; tracking_reference: string | null
  transport_mode: TransportMode; origin: string | null; destination: string | null; estimated_departure: string | null; actual_departure: string | null
  estimated_arrival: string | null; actual_arrival: string | null; status: ShipmentStatus; delay_reason: string | null; notes: string | null
  created_by_user_id: string; created_at: string; updated_at: string
}
export interface ShipmentMilestone { id: string; organization_id: string; order_id: string; shipment_id: string; name: string; description: string | null; occurred_at: string; created_by_user_id: string; created_at: string }
export interface GoodsReceiptLine { id: string; order_id: string; receipt_id: string; order_item_id: string; quantity_received: string | number; product_id: string; product_sku: string; product_name: string }
export interface GoodsReceipt { id: string; organization_id: string; order_id: string; location_id: string; receipt_reference: string; idempotency_key: string; received_at: string; notes: string | null; received_by_user_id: string; items: GoodsReceiptLine[] }
export interface ImportDocument {
  id: string; organization_id: string; order_id: string; document_reference: string; document_type: string; file_name: string
  content_type: string; file_size: number; verification_status: DocumentVerificationStatus; verification_notes: string | null
  expiry_date: string | null; uploaded_by_user_id: string; verified_by_user_id: string | null; verified_at: string | null; created_at: string
}
