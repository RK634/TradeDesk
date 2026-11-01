export type RelatedEntityType = 'import_order' | 'import_shipment' | 'export_order' | 'export_shipment'
export type VerificationStatus = 'pending' | 'verified' | 'rejected'
export interface DocumentVersion {
  id: string
  version_number: number
  file_name: string
  content_type: string
  file_size: number
  sha256: string
  uploaded_by_user_id: string
  created_at: string
}
export interface TradeDocument {
  id: string
  organization_id: string
  document_reference: string
  document_type: string
  title: string
  description: string | null
  related_entity_type: RelatedEntityType
  related_entity_id: string
  verification_status: VerificationStatus
  verification_notes: string | null
  expiry_date: string | null
  current_version: number
  uploaded_by_user_id: string
  verified_by_user_id: string | null
  verified_at: string | null
  created_at: string
  updated_at: string
  current_file_name: string
  current_content_type: string
  current_file_size: number
  versions: DocumentVersion[]
}
export interface DocumentRequirement {
  id: string
  organization_id: string
  related_entity_type: RelatedEntityType
  related_entity_id: string
  document_type: string
  label: string
  is_required: boolean
  created_by_user_id: string
  created_at: string
}
export interface DocumentCompliance {
  related_entity_type: RelatedEntityType
  related_entity_id: string
  required_count: number
  satisfied_count: number
  missing_count: number
  is_compliant: boolean
  items: Array<{
    requirement_id: string; document_type: string; label: string; is_required: boolean
    uploaded_count: number; verified_count: number; satisfied: boolean
  }>
}
export interface VerificationEvent {
  id: string; document_id: string; version_number: number; from_status: string; to_status: string
  notes: string | null; actor_user_id: string; created_at: string
}
