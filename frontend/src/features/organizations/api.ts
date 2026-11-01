import { apiDelete, apiGet, apiPatch, apiPost } from '@/features/auth/api'
import type { CreatedInvitation, OrganizationMember, OrganizationMembership, UserRole } from '@/features/auth/types'

export function getOrganizations() {
  return apiGet<OrganizationMembership[]>('/organizations')
}

export function createOrganization(name: string) {
  return apiPost<OrganizationMembership>('/organizations', { name })
}

export function getMembers(organizationId: string) {
  return apiGet<OrganizationMember[]>(`/organizations/${organizationId}/members`)
}

export function inviteMember(organizationId: string, email: string, role: Exclude<UserRole, 'organization_owner'>) {
  return apiPost<CreatedInvitation>(`/organizations/${organizationId}/invitations`, { email, role })
}

export function updateMember(organizationId: string, membershipId: string, patch: { role?: UserRole; is_active?: boolean }) {
  return apiPatch<OrganizationMember>(`/organizations/${organizationId}/members/${membershipId}`, patch)
}

export function revokeInvitation(organizationId: string, invitationId: string) {
  return apiDelete<void>(`/organizations/${organizationId}/invitations/${invitationId}`)
}
