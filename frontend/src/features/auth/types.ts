export type UserRole =
  | 'organization_owner'
  | 'administrator'
  | 'import_manager'
  | 'export_manager'
  | 'operations_staff'
  | 'finance_staff'
  | 'read_only'

export interface UserSummary {
  id: string
  email: string
  full_name: string
  is_active: boolean
  created_at: string
}

export interface OrganizationMembership {
  organization_id: string
  organization_name: string
  organization_slug: string
  membership_id: string
  role: UserRole
  is_active: boolean
}

export interface AuthMe {
  user: UserSummary
  organizations: OrganizationMembership[]
}

export interface AuthResult extends AuthMe {
  csrf_token: string
}

export interface OrganizationMember {
  membership_id: string
  user_id: string
  email: string
  full_name: string
  role: UserRole
  is_active: boolean
  joined_at: string
}

export interface InvitationPreview {
  email: string
  organization_name: string
  role: Exclude<UserRole, 'organization_owner'>
  expires_at: string
  user_exists: boolean
}

export interface CreatedInvitation {
  invitation_id: string
  email: string
  role: Exclude<UserRole, 'organization_owner'>
  invitation_token: string
  expires_at: string
}
