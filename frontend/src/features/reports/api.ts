import { apiGet } from '@/features/auth/api'

export interface FinancialCurrencySummary {
  currency: string
  receivables_outstanding: string
  payables_outstanding: string
  overdue_receivables: string
  overdue_payables: string
}

export interface ReportSummary {
  start_date: string
  end_date: string
  imports: { total: number; by_status: Array<{ status: string; count: number }> }
  exports: { total: number; by_status: Array<{ status: string; count: number }> }
  shipments: { total: number; delayed: number; import_total: number; export_total: number }
  inventory: { balance_rows: number; low_stock_rows: number }
  missing_required_documents: number
  financial: FinancialCurrencySummary[] | null
}

export interface ImportCostReportRow {
  record_id: string
  reference: string
  supplier_name: string
  status: string
  currency: string
  estimated_goods_total: string
  estimated_costs: string
  estimated_total: string
  actual_costs: string
  actual_total: string
  variance: string
  created_at: string
}

export interface PartnerReportRow {
  direction: 'import' | 'export'
  partner_name: string
  currency: string
  order_count: number
  order_value: string
}

export interface ShipmentPerformanceRow {
  shipment_id: string
  direction: 'import' | 'export'
  shipment_reference: string
  order_reference: string
  partner_name: string
  status: string
  transport_mode: string
  estimated_arrival: string | null
  actual_arrival: string | null
  days_late: number | null
  delay_reason: string | null
  created_at: string
}

export interface MissingDocumentReportRow {
  requirement_id: string
  related_entity_type: string
  related_entity_id: string
  record_reference: string
  partner_name: string
  document_type: string
  label: string
  created_at: string
}

export interface ReportOrderRow {
  record_id: string
  direction: 'import' | 'export'
  reference: string
  partner_name: string
  status: string
  currency: string
  order_total: string
  created_at: string
}

export interface InventoryReportRow {
  product_id: string
  sku: string
  product_name: string
  location_id: string
  location_code: string
  location_name: string
  quantity_on_hand: string
  reserved_quantity: string
  available_quantity: string
  reorder_threshold: string
  is_low_stock: boolean
}

const queryString = (values: Record<string, string | undefined>) => {
  const params = new URLSearchParams()
  Object.entries(values).forEach(([key, value]) => { if (value) params.set(key, value) })
  return params.toString()
}

export function getReportSummary(organizationId: string, startDate: string, endDate: string) {
  return apiGet<ReportSummary>(`/reports/summary?${queryString({ organization_id: organizationId, start_date: startDate, end_date: endDate })}`)
}

export function getOrderReport(organizationId: string, startDate: string, endDate: string) {
  return apiGet<ReportOrderRow[]>(`/reports/orders?${queryString({ organization_id: organizationId, start_date: startDate, end_date: endDate })}`)
}

export function getInventoryReport(organizationId: string, lowStockOnly = false) {
  return apiGet<InventoryReportRow[]>(`/reports/inventory?${queryString({ organization_id: organizationId, low_stock_only: lowStockOnly ? 'true' : undefined })}`)
}

export function getImportCostReport(organizationId: string, startDate: string, endDate: string) {
  return apiGet<ImportCostReportRow[]>(`/reports/import-costs?${queryString({ organization_id: organizationId, start_date: startDate, end_date: endDate })}`)
}

export function getPartnerReport(organizationId: string, startDate: string, endDate: string) {
  return apiGet<PartnerReportRow[]>(`/reports/partners?${queryString({ organization_id: organizationId, start_date: startDate, end_date: endDate })}`)
}

export function getShipmentPerformanceReport(organizationId: string, startDate: string, endDate: string) {
  return apiGet<ShipmentPerformanceRow[]>(`/reports/shipment-performance?${queryString({ organization_id: organizationId, start_date: startDate, end_date: endDate })}`)
}

export function getMissingDocumentsReport(organizationId: string) {
  return apiGet<MissingDocumentReportRow[]>(`/reports/missing-documents?${queryString({ organization_id: organizationId })}`)
}

export async function downloadReportCsv(organizationId: string, reportType: string, startDate?: string, endDate?: string) {
  const path = `/reports/csv?${queryString({ organization_id: organizationId, report_type: reportType, start_date: startDate, end_date: endDate })}`
  const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || '/api/v1'}${path}`, { credentials: 'include', headers: { Accept: 'text/csv' } })
  if (!response.ok) {
    if (response.status === 401) window.dispatchEvent(new Event('auth:unauthorized'))
    let message = `CSV export failed (${response.status}).`
    try {
      const payload = await response.json() as { detail?: string }
      if (payload.detail) message = payload.detail
    } catch { /* Use stable fallback for a non-JSON error response. */ }
    throw new Error(message)
  }
  const blob = await response.blob()
  const disposition = response.headers.get('Content-Disposition') || ''
  const fileName = disposition.match(/filename="?([^";]+)"?/i)?.[1] || `${reportType}.csv`
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = fileName
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
