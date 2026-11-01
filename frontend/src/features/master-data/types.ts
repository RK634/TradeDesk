export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface MasterDataRecord {
  id: string
  organization_id: string
  is_active: boolean
  created_at: string
  updated_at?: string
  [key: string]: unknown
}

export interface CustomerRecord extends MasterDataRecord {
  customer_code: string | null
  name: string
  company_name: string | null
  email: string | null
  phone: string | null
  country: string | null
  currency: string
  payment_terms_days: number
}

export interface SupplierRecord extends MasterDataRecord {
  supplier_code: string | null
  name: string
  company_name: string | null
  email: string | null
  phone: string | null
  country: string | null
  currency: string
  payment_terms_days: number
}

export interface ProductRecord extends MasterDataRecord {
  sku: string
  name: string
  description: string | null
  category: string | null
  unit_of_measure: string
  purchase_price: string | number
  selling_price: string | number
  currency: string
  reorder_threshold: string | number
}

export interface LocationRecord extends MasterDataRecord {
  code: string
  name: string
  description: string | null
  address: string | null
}

export interface InventoryBalanceRecord {
  id: string
  organization_id: string
  product_id: string
  product_sku: string
  product_name: string
  location_id: string
  location_code: string
  location_name: string
  quantity_on_hand: string | number
  reserved_quantity: string | number
  available_quantity: string | number
  reorder_threshold: string | number
  is_low_stock: boolean
  updated_at: string
}

export type InventoryMovementType =
  | 'goods_received'
  | 'goods_dispatched'
  | 'reservation'
  | 'reservation_release'
  | 'adjustment_increase'
  | 'adjustment_decrease'
  | 'return'

export interface InventoryMovementRecord {
  id: string
  organization_id: string
  product_id: string
  location_id: string
  movement_type: InventoryMovementType
  quantity_delta: string | number
  reserved_delta: string | number
  quantity_on_hand_after: string | number
  reserved_quantity_after: string | number
  idempotency_key: string
  source_type: string | null
  source_reference: string | null
  notes: string | null
  created_by_user_id: string
  created_at: string
}
