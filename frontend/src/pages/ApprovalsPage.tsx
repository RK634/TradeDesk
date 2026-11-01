import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, Check, ClipboardCheck, RefreshCw, RotateCcw, Save, ShieldCheck, X } from 'lucide-react'
import { Link, useOutletContext } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import type { AppShellOutletContext } from '@/components/layout/AppShell'
import { decideApproval, listApprovalRules, listApprovals, updateApprovalRule } from '@/features/workflow/api'
import type { ApprovalRecord, ApprovalRule } from '@/features/workflow/types'

const fieldClass = 'w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-sky-400 focus:ring-2 focus:ring-sky-100'
const roles = ['organization_owner', 'administrator', 'import_manager', 'export_manager', 'operations_staff', 'finance_staff']
const roleLabels: Record<string, string> = {
  organization_owner: 'Organization owner', administrator: 'Administrator', import_manager: 'Import manager',
  export_manager: 'Export manager', operations_staff: 'Operations staff', finance_staff: 'Finance staff',
}
const actionLabels: Record<string, string> = {
  import_order: 'Import orders', export_order: 'Export orders', invoice: 'Invoices', payment: 'Payments', task: 'Tasks', custom: 'Other actions',
}
const statusClass: Record<string, string> = {
  submitted: 'bg-amber-50 text-amber-700', approved: 'bg-emerald-50 text-emerald-700',
  rejected: 'bg-rose-50 text-rose-700', returned: 'bg-sky-50 text-sky-700', cancelled: 'bg-slate-100 text-slate-600',
}

function RuleEditor({ rule, organizationId, onSaved }: { rule: ApprovalRule; organizationId: string; onSaved: () => void }) {
  const [enabled, setEnabled] = useState(rule.is_enabled)
  const [selectedRoles, setSelectedRoles] = useState<string[]>(rule.required_roles)
  const [minimumAmount, setMinimumAmount] = useState(rule.minimum_amount === null ? '' : String(rule.minimum_amount))
  const [allowSelfApproval, setAllowSelfApproval] = useState(rule.allow_self_approval)
  const mutation = useMutation({
    mutationFn: () => updateApprovalRule(organizationId, rule.business_action, {
      is_enabled: enabled, required_roles: selectedRoles, minimum_amount: minimumAmount.trim() ? minimumAmount : null,
      allow_self_approval: allowSelfApproval,
    }),
    onSuccess: onSaved,
  })
  useEffect(() => {
    setEnabled(rule.is_enabled)
    setSelectedRoles(rule.required_roles)
    setMinimumAmount(rule.minimum_amount === null ? '' : String(rule.minimum_amount))
    setAllowSelfApproval(rule.allow_self_approval)
  }, [rule])

  function toggleRole(role: string) {
    setSelectedRoles((current) => current.includes(role) ? current.filter((value) => value !== role) : [...current, role])
  }

  return (
    <div className="rounded-xl border border-slate-200 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h4 className="text-sm font-semibold text-slate-900">{actionLabels[rule.business_action] ?? rule.business_action}</h4><p className="mt-1 text-xs text-slate-500">Choose who may decide requests for this action.</p></div>
        <label className="flex items-center gap-2 text-xs font-medium text-slate-600"><input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} />Approval enabled</label>
      </div>
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <fieldset className="space-y-2"><legend className="mb-2 text-xs font-semibold text-slate-600">Approver roles</legend>
          <div className="grid gap-2 sm:grid-cols-2">{roles.map((role) => <label key={role} className="flex items-center gap-2 text-xs text-slate-700"><input type="checkbox" checked={selectedRoles.includes(role)} onChange={() => toggleRole(role)} />{roleLabels[role]}</label>)}</div>
        </fieldset>
        <div className="space-y-3">
          <label className="block space-y-1.5 text-xs font-semibold text-slate-600">Minimum transaction amount (optional)<input className={fieldClass} type="number" min="0" step="0.01" value={minimumAmount} onChange={(event) => setMinimumAmount(event.target.value)} placeholder="No minimum" /></label>
          <label className="flex items-center gap-2 text-xs text-slate-700"><input type="checkbox" checked={allowSelfApproval} onChange={(event) => setAllowSelfApproval(event.target.checked)} />Allow requester to approve their own request</label>
        </div>
      </div>
      {mutation.isError && <p role="alert" className="mt-3 text-xs text-rose-700">{mutation.error instanceof Error ? mutation.error.message : 'Could not save approval rule.'}</p>}
      <div className="mt-4 flex justify-end"><Button size="sm" onClick={() => mutation.mutate()} disabled={mutation.isPending || selectedRoles.length === 0}><Save size={14} />{mutation.isPending ? 'Saving…' : 'Save rule'}</Button></div>
    </div>
  )
}

export function ApprovalsPage() {
  const { selectedOrganizationId, selectedOrganization } = useOutletContext<AppShellOutletContext>()
  const queryClient = useQueryClient()
  const [statusFilter, setStatusFilter] = useState('submitted')
  const [notes, setNotes] = useState<Record<string, string>>({})
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const canManageRules = ['organization_owner', 'administrator'].includes(selectedOrganization?.role ?? '')
  const approvalsQuery = useQuery({ queryKey: ['workflow', 'approvals', selectedOrganizationId, statusFilter], queryFn: () => listApprovals(selectedOrganizationId, statusFilter), enabled: Boolean(selectedOrganizationId), retry: false })
  const rulesQuery = useQuery({ queryKey: ['workflow', 'approval-rules', selectedOrganizationId], queryFn: () => listApprovalRules(selectedOrganizationId), enabled: Boolean(selectedOrganizationId) && canManageRules, retry: false })
  const decisionMutation = useMutation({
    mutationFn: ({ approval, status }: { approval: ApprovalRecord; status: 'approved' | 'rejected' | 'returned' }) => decideApproval(selectedOrganizationId, approval.id, status, notes[approval.id]?.trim() || undefined),
    onSuccess: (approval) => {
      setNotice(`“${approval.title}” was ${approval.status}.`); setError('')
      void queryClient.invalidateQueries({ queryKey: ['workflow', 'approvals', selectedOrganizationId] })
      void queryClient.invalidateQueries({ queryKey: ['workflow', 'notifications', selectedOrganizationId] })
      void queryClient.invalidateQueries({ queryKey: ['workflow', 'unread-count', selectedOrganizationId] })
    },
    onError: (reason) => { setError(reason instanceof Error ? reason.message : 'Approval decision failed.'); setNotice('') },
  })
  const approvals = approvalsQuery.data ?? []

  return <div className="space-y-6">
    <div className="flex flex-wrap items-end justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-[0.15em] text-sky-700">Control & authorization</p><h2 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">Approvals</h2><p className="mt-1 text-sm text-slate-500">Review requests, record decisions, and configure who can approve business actions.</p></div><Button variant="outline" onClick={() => void approvalsQuery.refetch()}><RefreshCw size={15} />Refresh</Button></div>
    {notice && <div role="status" className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{notice}</div>}
    {error && <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}
    <Card><CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3"><div><CardTitle className="flex items-center gap-2 text-base"><ClipboardCheck size={17} />Approval inbox</CardTitle><CardDescription>Import and export approval decisions are completed in their order workflows to preserve inventory controls.</CardDescription></div><select aria-label="Approval status filter" className="w-auto rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="submitted">Pending</option><option value="approved">Approved</option><option value="rejected">Rejected</option><option value="returned">Returned</option><option value="cancelled">Cancelled</option><option value="all">All statuses</option></select></CardHeader>
      <CardContent className="space-y-3">{approvalsQuery.isLoading ? <p className="py-8 text-center text-sm text-slate-500">Loading approval requests…</p> : approvalsQuery.isError ? <div role="alert" className="rounded-lg bg-rose-50 p-4 text-sm text-rose-700">{approvalsQuery.error instanceof Error ? approvalsQuery.error.message : 'Unable to load approvals.'}</div> : approvals.length === 0 ? <div className="rounded-xl border border-dashed border-slate-300 px-5 py-10 text-center"><ShieldCheck size={28} className="mx-auto text-slate-300" /><p className="mt-3 text-sm font-semibold text-slate-700">No {statusFilter === 'submitted' ? 'pending ' : ''}approval requests</p><p className="mt-1 text-xs text-slate-500">New requests will appear here when a workflow requires review.</p></div> : approvals.map((approval) => {
        const isOrderApproval = approval.related_entity_type === 'import_order' || approval.related_entity_type === 'export_order'
        const note = notes[approval.id] ?? ''
        return <article key={approval.id} className="rounded-xl border border-slate-200 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0"><h3 className="text-sm font-semibold text-slate-900">{approval.title}</h3><p className="mt-1 text-xs text-slate-500">{actionLabels[approval.business_action] ?? approval.business_action} · Requested by {approval.requested_by_name} · {new Date(approval.submitted_at).toLocaleString()}</p>{approval.request_note && <p className="mt-2 text-sm text-slate-600">{approval.request_note}</p>}{approval.requested_amount !== null && approval.requested_amount !== undefined && <p className="mt-2 text-xs font-semibold text-slate-700">Requested amount: {Number(approval.requested_amount).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} {approval.currency ?? ''}</p>}</div><span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${statusClass[approval.status] ?? statusClass.submitted}`}>{approval.status}</span></div>
          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-500"><span>{approval.events.length} history event(s)</span>{approval.decided_by_name && <span>· Decided by {approval.decided_by_name}</span>}{approval.decision_note && <span>· {approval.decision_note}</span>}
            {isOrderApproval && <Link className="ml-auto inline-flex items-center gap-1 font-semibold text-sky-700 hover:underline" to={approval.related_entity_type === 'import_order' ? '/app/imports' : '/app/exports'}>Open order workflow <ArrowRight size={13} /></Link>}
          </div>
          {approval.status === 'submitted' && !isOrderApproval && <div className="mt-4 space-y-2 border-t border-slate-100 pt-3"><label className="block space-y-1 text-xs font-medium text-slate-600">Decision note (required for reject or return)<textarea className={fieldClass} rows={2} value={note} onChange={(event) => setNotes((current) => ({ ...current, [approval.id]: event.target.value }))} maxLength={2000} placeholder="Add your review comments…" /></label><div className="flex flex-wrap justify-end gap-2"><Button variant="outline" size="sm" disabled={decisionMutation.isPending || !note.trim()} onClick={() => decisionMutation.mutate({ approval, status: 'returned' })}><RotateCcw size={14} />Return</Button><Button variant="outline" size="sm" disabled={decisionMutation.isPending || !note.trim()} onClick={() => decisionMutation.mutate({ approval, status: 'rejected' })}><X size={14} />Reject</Button><Button size="sm" disabled={decisionMutation.isPending} onClick={() => decisionMutation.mutate({ approval, status: 'approved' })}><Check size={14} />Approve</Button></div></div>}
        </article>
      })}</CardContent>
    </Card>
    {canManageRules && <Card><CardHeader><CardTitle className="text-base">Approval rules</CardTitle><CardDescription>Rules are enforced by the backend. Changes take effect on new submissions and pending decisions.</CardDescription></CardHeader><CardContent className="space-y-3">{rulesQuery.isLoading ? <p className="text-sm text-slate-500">Loading approval rules…</p> : rulesQuery.isError ? <p role="alert" className="text-sm text-rose-700">{rulesQuery.error instanceof Error ? rulesQuery.error.message : 'Could not load approval rules.'}</p> : (rulesQuery.data ?? []).map((rule) => <RuleEditor key={rule.business_action} rule={rule} organizationId={selectedOrganizationId} onSaved={() => { setNotice(`${actionLabels[rule.business_action] ?? rule.business_action} approval rule saved.`); void queryClient.invalidateQueries({ queryKey: ['workflow', 'approval-rules', selectedOrganizationId] }) }} />)}</CardContent></Card>}
  </div>
}
