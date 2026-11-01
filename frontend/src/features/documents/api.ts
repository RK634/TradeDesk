import { apiDelete, apiGet, apiPatch, apiPost, apiUpload } from '@/features/auth/api'
import type { DocumentCompliance, DocumentRequirement, RelatedEntityType, TradeDocument, VerificationEvent } from './types'

function orgQuery(organizationId: string) { return new URLSearchParams({ organization_id: organizationId }).toString() }
export function listDocuments(organizationId: string) {
  return apiGet<TradeDocument[]>(`/documents?${orgQuery(organizationId)}`)
}
export function uploadDocument(organizationId: string, form: FormData) {
  return apiUpload<TradeDocument>(`/documents?${orgQuery(organizationId)}`, form)
}
export function uploadDocumentVersion(organizationId: string, documentId: string, form: FormData) {
  return apiUpload<TradeDocument>(`/documents/${documentId}/versions?${orgQuery(organizationId)}`, form)
}
export function verifyDocument(organizationId: string, documentId: string, verificationStatus: 'verified' | 'rejected', notes: string) {
  return apiPatch<TradeDocument>(`/documents/${documentId}/verification?${orgQuery(organizationId)}`, { verification_status: verificationStatus, verification_notes: notes || null })
}
export function deleteDocument(organizationId: string, documentId: string) {
  return apiDelete<void>(`/documents/${documentId}?${orgQuery(organizationId)}`)
}
export function listDocumentRequirements(organizationId: string, type: RelatedEntityType, id: string) {
  const query = new URLSearchParams({ organization_id: organizationId, related_entity_type: type, related_entity_id: id })
  return apiGet<DocumentRequirement[]>(`/documents/requirements?${query.toString()}`)
}
export function createDocumentRequirement(organizationId: string, payload: Record<string, unknown>) {
  return apiPost<DocumentRequirement>(`/documents/requirements?${orgQuery(organizationId)}`, payload)
}
export function deleteDocumentRequirement(organizationId: string, requirementId: string) {
  return apiDelete<void>(`/documents/requirements/${requirementId}?${orgQuery(organizationId)}`)
}
export function getDocumentCompliance(organizationId: string, type: RelatedEntityType, id: string) {
  const query = new URLSearchParams({ organization_id: organizationId, related_entity_type: type, related_entity_id: id })
  return apiGet<DocumentCompliance>(`/documents/compliance?${query.toString()}`)
}
export function listVerificationHistory(organizationId: string, documentId: string) {
  return apiGet<VerificationEvent[]>(`/documents/${documentId}/verification-history?${orgQuery(organizationId)}`)
}
export async function downloadDocument(organizationId: string, documentId: string, version?: number) {
  const query = new URLSearchParams({ organization_id: organizationId })
  if (version) query.set('version_number', String(version))
  const apiBase = import.meta.env.VITE_API_BASE_URL || '/api/v1'
  const response = await fetch(`${apiBase}/documents/${documentId}/download?${query.toString()}`, { credentials: 'include' })
  if (!response.ok) throw new Error(`Document download failed (${response.status}).`)
  const blob = await response.blob()
  const objectUrl = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = objectUrl
  const disposition = response.headers.get('content-disposition') ?? ''
  const encodedName = disposition.split('filename*=')[1]?.replace(/^UTF-8''/i, '')
  anchor.download = encodedName ? decodeURIComponent(encodedName) : 'document'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(objectUrl)
}
