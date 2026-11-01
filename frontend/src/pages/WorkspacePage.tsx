import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Building2, Check, ChevronDown, Copy, Globe2, LoaderCircle, LogOut, MailPlus, Plus, ShieldCheck, Users } from 'lucide-react'
import { Link, useNavigate, useOutletContext } from 'react-router-dom'
import type { AppShellOutletContext } from '@/components/layout/AppShell'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/features/auth/AuthProvider'
import type { CreatedInvitation, OrganizationMember, UserRole } from '@/features/auth/types'
import { createOrganization, getMembers, getOrganizations, inviteMember, updateMember } from '@/features/organizations/api'

const ROLE_LABELS: Record<UserRole, string> = {
  organization_owner: 'Organization Owner',
  administrator: 'Administrator',
  import_manager: 'Import Manager',
  export_manager: 'Export Manager',
  operations_staff: 'Operations Staff',
  finance_staff: 'Finance Staff',
  read_only: 'Read-Only User',
}
const INVITABLE_ROLES: Exclude<UserRole, 'organization_owner'>[] = [
  'administrator', 'import_manager', 'export_manager', 'operations_staff', 'finance_staff', 'read_only',
]
const QUERY_KEY = ['organization-members'] as const

export function WorkspacePage({ embedded = false }: { embedded?: boolean }) {
  const { auth, logout, refresh } = useAuth()
  const shellContext = useOutletContext<AppShellOutletContext | null>()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [localSelectedId, setLocalSelectedId] = useState('')
  const selectedId = embedded && shellContext ? shellContext.selectedOrganizationId : localSelectedId
  const setSelectedId = embedded && shellContext ? shellContext.setSelectedOrganizationId : setLocalSelectedId
  const [newOrganizationName, setNewOrganizationName] = useState('')
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState<Exclude<UserRole, 'organization_owner'>>('read_only')
  const [createdInvitation, setCreatedInvitation] = useState<CreatedInvitation | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const organizationsQuery = useQuery({ queryKey: ['organizations'], queryFn: getOrganizations, retry: false })
  const organizations = organizationsQuery.data ?? auth?.organizations ?? []
  const selectedOrganization = organizations.find((organization) => organization.organization_id === selectedId) ?? organizations[0]
  const organizationId = selectedOrganization?.organization_id ?? ''

  useEffect(() => {
    if (!selectedId && organizations.length > 0) setSelectedId(organizations[0].organization_id)
    if (selectedId && !organizations.some((item) => item.organization_id === selectedId) && organizations.length > 0) {
      setSelectedId(organizations[0].organization_id)
    }
  }, [organizations, selectedId])

  const role = selectedOrganization?.role
  const canManageMembers = role === 'organization_owner' || role === 'administrator'
  const memberQuery = useQuery({
    queryKey: [...QUERY_KEY, organizationId],
    queryFn: () => getMembers(organizationId),
    enabled: Boolean(organizationId) && canManageMembers,
    retry: false,
  })
  const createOrgMutation = useMutation({
    mutationFn: createOrganization,
    onSuccess: async (organization) => {
      setNewOrganizationName('')
      setSelectedId(organization.organization_id)
      setMessage('Organization created. You are its owner.')
      setError(null)
      await refresh()
      await organizationsQuery.refetch()
    },
    onError: (cause) => setError(cause instanceof Error ? cause.message : 'Could not create organization.'),
  })
  const inviteMutation = useMutation({
    mutationFn: (input: { email: string; role: Exclude<UserRole, 'organization_owner'> }) => inviteMember(organizationId, input.email, input.role),
    onSuccess: (invitation) => {
      setCreatedInvitation(invitation)
      setInviteEmail('')
      setMessage(`Invitation created for ${invitation.email}. The link is shown below; it has not been emailed automatically.`)
      setError(null)
    },
    onError: (cause) => setError(cause instanceof Error ? cause.message : 'Could not create invitation.'),
  })
  const updateMutation = useMutation({
    mutationFn: (input: { membershipId: string; patch: { role?: UserRole; is_active?: boolean } }) => updateMember(organizationId, input.membershipId, input.patch),
    onSuccess: async () => {
      setMessage('Member permissions updated.')
      setError(null)
      await queryClient.invalidateQueries({ queryKey: [...QUERY_KEY, organizationId] })
    },
    onError: (cause) => setError(cause instanceof Error ? cause.message : 'Could not update member.'),
  })

  const invitationUrl = useMemo(() => createdInvitation
    ? `${window.location.origin}/accept-invitation?token=${encodeURIComponent(createdInvitation.invitation_token)}`
    : '', [createdInvitation])

  async function onLogout() {
    try {
      await logout()
      navigate('/login', { replace: true })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Sign out failed. Retry once more.')
    }
  }

  async function copyInvitationLink() {
    try {
      await navigator.clipboard.writeText(invitationUrl)
      setMessage('Invitation link copied to clipboard.')
    } catch {
      setMessage('Clipboard access was blocked. Select and copy the invitation link from the field below.')
    }
  }

  const members: OrganizationMember[] = memberQuery.data ?? []
  const roleOptions = role === 'organization_owner' ? INVITABLE_ROLES : INVITABLE_ROLES.filter((item) => item !== 'administrator')

  return (
    <main className={embedded ? 'min-w-0' : 'min-h-screen'}>
      {!embedded && <header className="border-b bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-4 sm:px-8">
          <Link to="/" className="flex items-center gap-3 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary text-white"><Globe2 size={21} /></span>
            <span><span className="block font-bold">TradeDesk</span><span className="block text-xs text-muted-foreground">Secure workspace</span></span>
          </Link>
          <div className="flex items-center gap-3">
            <div className="hidden text-right sm:block"><p className="text-sm font-semibold">{auth?.user.full_name}</p><p className="text-xs text-muted-foreground">{auth?.user.email}</p></div>
            <Button variant="outline" size="sm" onClick={onLogout}><LogOut size={15} /> Sign out</Button>
          </div>
        </div>
      </header>}

      <div className={embedded ? 'space-y-1' : 'mx-auto max-w-7xl px-4 py-8 sm:px-8 sm:py-10'}>
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
          <div>
            <p className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.16em] text-primary"><ShieldCheck size={14} /> Organization administration</p>
            <h1 className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">{embedded ? 'Organization & members' : 'Your workspace'}</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">Manage your organization profile, employee invitations, membership status, and access roles.</p>
          </div>
          {!embedded && organizations.length > 0 && (
            <label className="flex min-w-0 flex-col gap-1.5 text-sm font-medium md:min-w-64">
              Active organization
              <span className="relative"><Building2 className="pointer-events-none absolute left-3 top-3 text-muted-foreground" size={16} /><select aria-label="Active organization" value={organizationId} onChange={(event) => { setSelectedId(event.target.value); setCreatedInvitation(null); setMessage(null); setError(null) }} className="h-11 w-full appearance-none rounded-md border bg-white pl-9 pr-9 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring">{organizations.map((organization) => <option key={organization.organization_id} value={organization.organization_id}>{organization.organization_name}</option>)}</select><ChevronDown className="pointer-events-none absolute right-3 top-3 text-muted-foreground" size={16} /></span>
            </label>
          )}
        </div>

        {(message || error) && <div className={`mt-6 rounded-lg border p-3 text-sm ${error ? 'border-rose-200 bg-rose-50 text-rose-800' : 'border-emerald-200 bg-emerald-50 text-emerald-800'}`} role={error ? 'alert' : 'status'}>{error || message}<button className="ml-3 font-semibold underline underline-offset-2" onClick={() => { setMessage(null); setError(null) }}>Dismiss</button></div>}

        {error && error.toLowerCase().includes('session') && <p className="mt-2 text-sm"><Link to="/login" className="underline">Sign in again</Link></p>}

        <section className="mt-8 grid gap-5 lg:grid-cols-[0.8fr_1.2fr]">
          <div className="space-y-5">
            <div className="rounded-xl border bg-white p-5 shadow-sm">
              <div className="flex items-center gap-3"><span className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50 text-primary"><Building2 size={19} /></span><div><h2 className="font-semibold">Organization details</h2><p className="text-xs text-muted-foreground">Your current access</p></div></div>
              {selectedOrganization ? (
                <dl className="mt-5 space-y-3 text-sm">
                  <div className="flex justify-between gap-4"><dt className="text-muted-foreground">Name</dt><dd className="text-right font-medium">{selectedOrganization.organization_name}</dd></div>
                  <div className="flex justify-between gap-4"><dt className="text-muted-foreground">Slug</dt><dd className="font-mono text-xs">{selectedOrganization.organization_slug}</dd></div>
                  <div className="flex justify-between gap-4"><dt className="text-muted-foreground">Your role</dt><dd><span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold">{role ? ROLE_LABELS[role] : 'Member'}</span></dd></div>
                </dl>
              ) : <p className="mt-4 text-sm text-muted-foreground">No active organization memberships were found.</p>}
            </div>

            <div className="rounded-xl border bg-white p-5 shadow-sm">
              <div className="flex items-center gap-3"><span className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-50 text-indigo-700"><Plus size={19} /></span><div><h2 className="font-semibold">Create an organization</h2><p className="text-xs text-muted-foreground">You will become its owner.</p></div></div>
              <form className="mt-4 space-y-3" onSubmit={(event) => { event.preventDefault(); if (newOrganizationName.trim()) createOrgMutation.mutate(newOrganizationName.trim()) }}>
                <label htmlFor="new-organization" className="block text-sm font-medium">Organization name</label>
                <input id="new-organization" value={newOrganizationName} onChange={(event) => setNewOrganizationName(event.target.value)} minLength={2} maxLength={160} required className="h-10 w-full rounded-md border px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring" placeholder="Example Trading GmbH" />
                <Button type="submit" variant="outline" className="w-full" disabled={createOrgMutation.isPending || newOrganizationName.trim().length < 2}>{createOrgMutation.isPending ? <LoaderCircle className="animate-spin" size={15} /> : <Plus size={15} />} Create organization</Button>
              </form>
            </div>
          </div>

          <div className="rounded-xl border bg-white shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b p-5">
              <div className="flex items-center gap-3"><span className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700"><Users size={19} /></span><div><h2 className="font-semibold">Members and permissions</h2><p className="text-xs text-muted-foreground">Role assignment is enforced by the backend.</p></div></div>
              {canManageMembers && <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700">Admin access</span>}
            </div>
            {!canManageMembers ? (
              <div className="p-6 text-sm leading-6 text-muted-foreground">Your role can access authorized trade data but cannot view or administer organization members.</div>
            ) : memberQuery.isPending ? (
              <div className="flex items-center gap-2 p-6 text-sm text-muted-foreground" role="status"><LoaderCircle className="animate-spin" size={16} /> Loading members…</div>
            ) : memberQuery.isError ? (
              <div className="p-6 text-sm text-rose-700" role="alert">{memberQuery.error instanceof Error ? memberQuery.error.message : 'Could not load members.'}</div>
            ) : (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[600px] text-left text-sm">
                    <thead className="bg-slate-50 text-xs uppercase tracking-wide text-muted-foreground"><tr><th className="px-5 py-3 font-semibold">Member</th><th className="px-4 py-3 font-semibold">Role</th><th className="px-4 py-3 font-semibold">Status</th></tr></thead>
                    <tbody className="divide-y">
                      {members.map((member) => {
                        const immutable = member.role === 'organization_owner' || member.user_id === auth?.user.id
                        const optionsForActor = role === 'organization_owner' ? INVITABLE_ROLES : INVITABLE_ROLES.filter((item) => item !== 'administrator')
                        return <tr key={member.membership_id}>
                          <td className="px-5 py-4"><p className="font-medium">{member.full_name}</p><p className="mt-1 text-xs text-muted-foreground">{member.email}</p></td>
                          <td className="px-4 py-4"><select aria-label={`Role for ${member.email}`} disabled={immutable || updateMutation.isPending} value={member.role} onChange={(event) => updateMutation.mutate({ membershipId: member.membership_id, patch: { role: event.target.value as UserRole } })} className="h-9 max-w-48 rounded-md border bg-white px-2 text-xs disabled:bg-slate-50 disabled:text-muted-foreground">{member.role === 'organization_owner' && <option value="organization_owner">Organization Owner</option>}{optionsForActor.map((item) => <option key={item} value={item}>{ROLE_LABELS[item]}</option>)}</select></td>
                          <td className="px-4 py-4">{member.role === 'organization_owner' ? <span className="text-xs font-semibold text-primary">Protected owner</span> : <button type="button" disabled={member.user_id === auth?.user.id || updateMutation.isPending} onClick={() => updateMutation.mutate({ membershipId: member.membership_id, patch: { is_active: !member.is_active } })} className={`rounded-full px-2.5 py-1 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-60 ${member.is_active ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-600'}`}>{member.is_active ? 'Active · Deactivate' : 'Inactive · Activate'}</button>}</td>
                        </tr>
                      })}
                      {members.length === 0 && <tr><td colSpan={3} className="px-5 py-8 text-center text-sm text-muted-foreground">No members found.</td></tr>}
                    </tbody>
                  </table>
                </div>
                <div className="border-t p-5">
                  <div className="mb-4 flex items-center gap-2"><MailPlus size={17} className="text-primary" /><h3 className="font-semibold">Invite a teammate</h3></div>
                  <form className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_190px_auto]" onSubmit={(event) => { event.preventDefault(); inviteMutation.mutate({ email: inviteEmail.trim(), role: inviteRole }) }}>
                    <label className="sr-only" htmlFor="invite-email">Teammate email</label>
                    <input id="invite-email" type="email" required value={inviteEmail} onChange={(event) => setInviteEmail(event.target.value)} className="h-10 min-w-0 rounded-md border px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring" placeholder="teammate@company.com" />
                    <label className="sr-only" htmlFor="invite-role">Role for teammate</label>
                    <select id="invite-role" value={inviteRole} onChange={(event) => setInviteRole(event.target.value as Exclude<UserRole, 'organization_owner'>)} className="h-10 rounded-md border bg-white px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring">{roleOptions.map((item) => <option key={item} value={item}>{ROLE_LABELS[item]}</option>)}</select>
                    <Button type="submit" disabled={!inviteEmail.trim() || inviteMutation.isPending}>{inviteMutation.isPending ? <LoaderCircle className="animate-spin" size={15} /> : <MailPlus size={15} />} Invite</Button>
                  </form>
                  <p className="mt-2 text-xs leading-5 text-muted-foreground">Invitations expire after the configured period. Email delivery is not configured yet; copy the one-time link and send it through an approved channel.</p>
                  {createdInvitation && <div className="mt-4 rounded-lg border bg-slate-50 p-3">
                    <p className="text-sm font-semibold">Invitation ready for {createdInvitation.email}</p>
                    <label htmlFor="invitation-link" className="mt-3 block text-xs font-medium text-muted-foreground">One-time invitation link</label>
                    <input id="invitation-link" readOnly value={invitationUrl} onFocus={(event) => event.currentTarget.select()} className="mt-1 h-10 w-full rounded-md border bg-white px-3 text-xs" />
                    <Button variant="outline" size="sm" className="mt-2" onClick={copyInvitationLink}><Copy size={14} /> Copy link</Button>
                    <p className="mt-2 flex items-center gap-1 text-xs text-muted-foreground"><Check size={13} /> The raw token is shown only in this response; store and share the link carefully.</p>
                  </div>}
                </div>
              </>
            )}
          </div>
        </section>
        <footer className="mt-8 flex flex-wrap items-center justify-between gap-2 border-t pt-5 text-xs text-muted-foreground"><span>TradeDesk · Workspace administration</span><span>Authentication · Organizations · Role-based access</span></footer>
      </div>
    </main>
  )
}
