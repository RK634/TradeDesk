import { apiGet, apiPatch, apiPost } from '@/features/auth/api'
import type { FinancialAuditEvent, InvoicePage, InvoiceRecord, PaymentPage, PaymentRecord } from './types'

function orgQuery(organizationId: string) {
  return new URLSearchParams({ organization_id: organizationId }).toString()
}

export function listInvoices(organizationId: string, search = '', status = 'all', invoiceType = 'all') {
  const query = new URLSearchParams({ organization_id: organizationId, page: '1', page_size: '100' })
  if (search.trim()) query.set('search', search.trim())
  if (status !== 'all') query.set('status', status)
  if (invoiceType !== 'all') query.set('invoice_type', invoiceType)
  return apiGet<InvoicePage>(`/invoices?${query.toString()}`)
}

export function createInvoice(organizationId: string, payload: Record<string, unknown>) {
  return apiPost<InvoiceRecord>(`/invoices?${orgQuery(organizationId)}`, payload)
}

export function updateInvoice(organizationId: string, invoiceId: string, payload: Record<string, unknown>) {
  return apiPatch<InvoiceRecord>(`/invoices/${invoiceId}?${orgQuery(organizationId)}`, payload)
}

export function issueInvoice(organizationId: string, invoiceId: string) {
  return apiPost<InvoiceRecord>(`/invoices/${invoiceId}/issue?${orgQuery(organizationId)}`, {})
}

export function voidInvoice(organizationId: string, invoiceId: string, reason: string) {
  return apiPost<InvoiceRecord>(`/invoices/${invoiceId}/void?${orgQuery(organizationId)}`, { reason })
}

export function getInvoiceAudit(organizationId: string, invoiceId: string) {
  return apiGet<FinancialAuditEvent[]>(`/invoices/${invoiceId}/audit?${orgQuery(organizationId)}`)
}

export function listPayments(organizationId: string, search = '', status = 'all', paymentType = 'all') {
  const query = new URLSearchParams({ organization_id: organizationId, page: '1', page_size: '100' })
  if (search.trim()) query.set('search', search.trim())
  if (status !== 'all') query.set('status', status)
  if (paymentType !== 'all') query.set('payment_type', paymentType)
  return apiGet<PaymentPage>(`/payments?${query.toString()}`)
}

export function createPayment(organizationId: string, payload: Record<string, unknown>) {
  return apiPost<PaymentRecord>(`/payments?${orgQuery(organizationId)}`, payload)
}

export function allocateExistingPayment(organizationId: string, paymentId: string, payload: Record<string, unknown>) {
  return apiPost<PaymentRecord>(`/payments/${paymentId}/allocations?${orgQuery(organizationId)}`, payload)
}

export function reversePayment(organizationId: string, paymentId: string, reason: string) {
  return apiPost<PaymentRecord>(`/payments/${paymentId}/reverse?${orgQuery(organizationId)}`, { reason })
}

export function getPaymentAudit(organizationId: string, paymentId: string) {
  return apiGet<FinancialAuditEvent[]>(`/payments/${paymentId}/audit?${orgQuery(organizationId)}`)
}
