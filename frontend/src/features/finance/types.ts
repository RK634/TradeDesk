export type InvoiceType = 'supplier' | 'customer'
export type InvoiceStatus = 'draft' | 'issued' | 'partially_paid' | 'paid' | 'overdue' | 'void'
export type PaymentType = 'incoming' | 'outgoing'
export type PaymentStatus = 'posted' | 'reversed'

export interface InvoiceLineInput {
  description: string
  quantity: string
  unit_price: string
  tax_rate: string
}

export interface InvoiceItem {
  id: string
  organization_id: string
  invoice_id: string
  line_number: number
  description: string
  quantity: string | number
  unit_price: string | number
  tax_rate: string | number
  net_amount: string | number
  tax_amount: string | number
  line_total: string | number
}

export interface InvoiceRecord {
  id: string
  organization_id: string
  invoice_number: string
  invoice_type: InvoiceType
  supplier_id: string | null
  customer_id: string | null
  partner_name: string
  import_order_id: string | null
  export_order_id: string | null
  order_reference: string | null
  status: InvoiceStatus
  issue_date: string
  due_date: string
  currency: string
  subtotal: string | number
  tax_amount: string | number
  discount_amount: string | number
  total_amount: string | number
  amount_paid: string | number
  outstanding_balance: string | number
  notes: string | null
  issued_by_user_id: string | null
  issued_at: string | null
  created_by_user_id: string
  created_at: string
  updated_at: string
  items: InvoiceItem[]
}

export interface InvoicePage { items: InvoiceRecord[]; total: number; page: number; page_size: number }

export interface PaymentAllocation {
  id: string
  invoice_id: string
  invoice_number: string
  invoice_currency: string
  allocated_payment_amount: string | number
  allocated_invoice_amount: string | number
  exchange_rate: string | number
  exchange_rate_date: string
}

export interface PaymentRecord {
  id: string
  organization_id: string
  payment_reference: string
  payment_type: PaymentType
  payment_date: string
  currency: string
  amount: string | number
  allocated_amount: string | number
  unallocated_amount: string | number
  payment_method: string
  external_reference: string | null
  status: PaymentStatus
  notes: string | null
  created_by_user_id: string
  reversed_by_user_id: string | null
  reversed_at: string | null
  reversal_reason: string | null
  created_at: string
  allocations: PaymentAllocation[]
}

export interface PaymentPage { items: PaymentRecord[]; total: number; page: number; page_size: number }

export interface FinancialAuditEvent {
  id: string
  entity_type: 'invoice' | 'payment'
  entity_id: string
  action: string
  details: Record<string, unknown>
  actor_user_id: string
  created_at: string
}
