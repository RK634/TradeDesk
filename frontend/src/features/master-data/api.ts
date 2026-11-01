import { apiGet, apiPatch, apiPost } from '@/features/auth/api'
import type {
  CustomerRecord, InventoryBalanceRecord, InventoryMovementRecord, LocationRecord,
  MasterDataRecord, Page, ProductRecord, SupplierRecord,
} from './types'

export type MasterDataResource = 'customers' | 'suppliers' | 'products' | 'inventory/locations'

export function listMasterData<T extends MasterDataRecord>(input: {
  resource: MasterDataResource
  organizationId: string
  search?: string
  active?: boolean | 'all'
}): Promise<Page<T>> {
  const query = new URLSearchParams({ organization_id: input.organizationId, page: '1', page_size: '100' })
  if (input.search?.trim()) query.set('search', input.search.trim())
  if (input.active !== undefined && input.active !== 'all') query.set('active', String(input.active))
  return apiGet<Page<T>>(`/${input.resource}?${query.toString()}`)
}

export function createMasterData<T>(resource: MasterDataResource, organizationId: string, payload: Record<string, string | number | boolean | null>): Promise<T> {
  const query = new URLSearchParams({ organization_id: organizationId })
  return apiPost<T>(`/${resource}?${query.toString()}`, payload)
}

export function updateMasterData<T>(resource: MasterDataResource, organizationId: string, recordId: string, payload: Record<string, string | number | boolean | null>): Promise<T> {
  const query = new URLSearchParams({ organization_id: organizationId })
  return apiPatch<T>(`/${resource}/${recordId}?${query.toString()}`, payload)
}

export function listCustomers(organizationId: string, search = '') {
  const query = new URLSearchParams({ organization_id: organizationId, page: '1', page_size: '100' })
  if (search.trim()) query.set('search', search.trim())
  return apiGet<Page<CustomerRecord>>(`/customers?${query.toString()}`)
}

export function listSuppliers(organizationId: string, search = '') {
  const query = new URLSearchParams({ organization_id: organizationId, page: '1', page_size: '100' })
  if (search.trim()) query.set('search', search.trim())
  return apiGet<Page<SupplierRecord>>(`/suppliers?${query.toString()}`)
}

export function listProducts(organizationId: string, search = '', active?: boolean) {
  const query = new URLSearchParams({ organization_id: organizationId, page: '1', page_size: '100' })
  if (search.trim()) query.set('search', search.trim())
  if (active !== undefined) query.set('active', String(active))
  return apiGet<Page<ProductRecord>>(`/products?${query.toString()}`)
}

export function listLocations(organizationId: string, active?: boolean) {
  const query = new URLSearchParams({ organization_id: organizationId, page: '1', page_size: '100' })
  if (active !== undefined) query.set('active', String(active))
  return apiGet<Page<LocationRecord>>(`/inventory/locations?${query.toString()}`)
}

export function listInventoryBalances(organizationId: string, lowStock?: boolean) {
  const query = new URLSearchParams({ organization_id: organizationId, page: '1', page_size: '100' })
  if (lowStock !== undefined) query.set('low_stock', String(lowStock))
  return apiGet<Page<InventoryBalanceRecord>>(`/inventory/balances?${query.toString()}`)
}

export function listInventoryMovements(organizationId: string) {
  const query = new URLSearchParams({ organization_id: organizationId, page: '1', page_size: '50' })
  return apiGet<Page<InventoryMovementRecord>>(`/inventory/movements?${query.toString()}`)
}

export function createInventoryMovement(payload: {
  organization_id: string
  product_id: string
  location_id: string
  movement_type: InventoryMovementRecord['movement_type']
  quantity: string
  idempotency_key: string
  notes?: string
}): Promise<InventoryMovementRecord> {
  return apiPost<InventoryMovementRecord>('/inventory/movements', payload)
}
