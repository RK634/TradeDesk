import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bell, CheckCheck, ExternalLink, Play, RefreshCw, Settings2 } from 'lucide-react'
import { Link, useOutletContext } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import type { AppShellOutletContext } from '@/components/layout/AppShell'
import { getNotificationPreferences, listAutomationLogs, listNotifications, markAllNotificationsRead, markNotificationRead, runAutomationNow, updateNotificationPreference } from '@/features/workflow/api'
import type { NotificationCategory } from '@/features/workflow/types'

const categoryLabels: Record<NotificationCategory, string> = {
  task: 'Tasks', approval: 'Approvals', invoice: 'Invoices & payments', shipment: 'Shipments',
  inventory: 'Inventory', document: 'Documents', order: 'Orders', system: 'System',
}
const categoryIcons: Record<NotificationCategory, string> = {
  task: 'Task', approval: 'Approval', invoice: 'Finance', shipment: 'Shipment',
  inventory: 'Inventory', document: 'Document', order: 'Order', system: 'System',
}

export function NotificationsPage() {
  const { selectedOrganizationId, selectedOrganization } = useOutletContext<AppShellOutletContext>()
  const queryClient = useQueryClient()
  const [unreadOnly, setUnreadOnly] = useState(false)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const isAdmin = ['organization_owner', 'administrator'].includes(selectedOrganization?.role ?? '')
  const notificationsQuery = useQuery({ queryKey: ['workflow', 'notifications', selectedOrganizationId, unreadOnly], queryFn: () => listNotifications(selectedOrganizationId, unreadOnly), enabled: Boolean(selectedOrganizationId), retry: false })
  const preferencesQuery = useQuery({ queryKey: ['workflow', 'notification-preferences', selectedOrganizationId], queryFn: () => getNotificationPreferences(selectedOrganizationId), enabled: Boolean(selectedOrganizationId), retry: false })
  const logsQuery = useQuery({ queryKey: ['workflow', 'automation-logs', selectedOrganizationId], queryFn: () => listAutomationLogs(selectedOrganizationId), enabled: Boolean(selectedOrganizationId) && isAdmin, retry: false })
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ['workflow', 'notifications', selectedOrganizationId] })
    void queryClient.invalidateQueries({ queryKey: ['workflow', 'unread-count', selectedOrganizationId] })
    void queryClient.invalidateQueries({ queryKey: ['workflow', 'automation-logs', selectedOrganizationId] })
  }
  const readMutation = useMutation({
    mutationFn: (notificationId: string) => markNotificationRead(selectedOrganizationId, notificationId),
    onSuccess: () => { setNotice('Notification marked as read.'); setError(''); refresh() },
    onError: (reason) => { setError(reason instanceof Error ? reason.message : 'Could not update notification.'); setNotice('') },
  })
  const readAllMutation = useMutation({
    mutationFn: () => markAllNotificationsRead(selectedOrganizationId),
    onSuccess: (result) => { setNotice(`${result.updated_count} notification(s) marked as read.`); setError(''); refresh() },
    onError: (reason) => { setError(reason instanceof Error ? reason.message : 'Could not mark notifications as read.'); setNotice('') },
  })
  const preferenceMutation = useMutation({
    mutationFn: ({ category, enabled }: { category: string; enabled: boolean }) => updateNotificationPreference(selectedOrganizationId, category, enabled),
    onSuccess: () => { setNotice('Notification preference saved.'); setError(''); void queryClient.invalidateQueries({ queryKey: ['workflow', 'notification-preferences', selectedOrganizationId] }) },
    onError: (reason) => { setError(reason instanceof Error ? reason.message : 'Could not save notification preference.'); setNotice('') },
  })
  const automationMutation = useMutation({
    mutationFn: () => runAutomationNow(selectedOrganizationId),
    onSuccess: () => { setNotice('Reminder checks completed. Existing events were not duplicated.'); setError(''); refresh() },
    onError: (reason) => { setError(reason instanceof Error ? reason.message : 'Automation run failed.'); setNotice('') },
  })
  const notifications = notificationsQuery.data?.items ?? []

  return <div className="space-y-6">
    <div className="flex flex-wrap items-end justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-[0.15em] text-sky-700">Workspace activity</p><h2 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">Notifications</h2><p className="mt-1 text-sm text-slate-500">Review important updates and control which in-app reminders you receive.</p></div><div className="flex gap-2"><Button variant="outline" onClick={() => void notificationsQuery.refetch()}><RefreshCw size={15} />Refresh</Button><Button variant="outline" disabled={readAllMutation.isPending || (notificationsQuery.data?.unread_count ?? 0) === 0} onClick={() => readAllMutation.mutate()}><CheckCheck size={15} />Read all</Button></div></div>
    {notice && <div role="status" className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{notice}</div>}
    {error && <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}
    <Card><CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3"><div><CardTitle className="flex items-center gap-2 text-base"><Bell size={17} />Your inbox</CardTitle><CardDescription>{notificationsQuery.data?.unread_count ?? 0} unread notification(s)</CardDescription></div><label className="flex items-center gap-2 text-xs font-medium text-slate-600"><input type="checkbox" checked={unreadOnly} onChange={(event) => setUnreadOnly(event.target.checked)} />Unread only</label></CardHeader><CardContent className="space-y-2">{notificationsQuery.isLoading ? <p className="py-8 text-center text-sm text-slate-500">Loading notifications…</p> : notificationsQuery.isError ? <p role="alert" className="text-sm text-rose-700">{notificationsQuery.error instanceof Error ? notificationsQuery.error.message : 'Could not load notifications.'}</p> : notifications.length === 0 ? <div className="rounded-xl border border-dashed border-slate-300 px-5 py-10 text-center"><Bell size={28} className="mx-auto text-slate-300" /><p className="mt-3 text-sm font-semibold text-slate-700">You're all caught up</p><p className="mt-1 text-xs text-slate-500">No notifications match this view.</p></div> : notifications.map((item) => <article key={item.id} className={`rounded-xl border p-4 ${item.read_at ? 'border-slate-100 bg-white' : 'border-sky-100 bg-sky-50/40'}`}><div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><span className="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-semibold text-slate-600">{categoryIcons[item.category]}</span><h3 className="text-sm font-semibold text-slate-900">{item.title}</h3>{!item.read_at && <span className="h-1.5 w-1.5 rounded-full bg-sky-500" aria-label="Unread" />}</div><p className="mt-2 text-sm text-slate-600">{item.message}</p><p className="mt-2 text-[11px] text-slate-400">{new Date(item.created_at).toLocaleString()}</p></div><div className="flex shrink-0 items-center gap-2">{item.link_path && <Link className="inline-flex items-center gap-1 text-xs font-semibold text-sky-700 hover:underline" to={item.link_path}>Open <ExternalLink size={12} /></Link>}{!item.read_at && <Button size="sm" variant="outline" disabled={readMutation.isPending} onClick={() => readMutation.mutate(item.id)}>Mark read</Button>}</div></div></article>)}</CardContent></Card>
    <Card><CardHeader><CardTitle className="flex items-center gap-2 text-base"><Settings2 size={17} />Notification preferences</CardTitle><CardDescription>Preferences apply to in-app notifications generated for your account in this organization.</CardDescription></CardHeader><CardContent className="grid gap-3 sm:grid-cols-2">{preferencesQuery.isLoading ? <p className="text-sm text-slate-500">Loading preferences…</p> : preferencesQuery.isError ? <p role="alert" className="text-sm text-rose-700">{preferencesQuery.error instanceof Error ? preferencesQuery.error.message : 'Could not load preferences.'}</p> : (preferencesQuery.data ?? []).map((preference) => <label key={preference.category} className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 px-3 py-3"><span className="text-sm font-medium text-slate-700">{categoryLabels[preference.category]}</span><input aria-label={`${categoryLabels[preference.category]} notifications`} type="checkbox" checked={preference.in_app_enabled} disabled={preferenceMutation.isPending} onChange={(event) => preferenceMutation.mutate({ category: preference.category, enabled: event.target.checked })} /></label>)}</CardContent></Card>
    {isAdmin && <Card><CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3"><div><CardTitle className="text-base">Automation monitor</CardTitle><CardDescription>Scheduled reminders are duplicate-safe, logged, and retried with a bounded attempt count.</CardDescription></div><Button disabled={automationMutation.isPending} onClick={() => automationMutation.mutate()}><Play size={14} />{automationMutation.isPending ? 'Running…' : 'Run reminders now'}</Button></CardHeader><CardContent className="space-y-2">{logsQuery.isLoading ? <p className="text-sm text-slate-500">Loading execution history…</p> : logsQuery.isError ? <p role="alert" className="text-sm text-rose-700">{logsQuery.error instanceof Error ? logsQuery.error.message : 'Could not load automation logs.'}</p> : (logsQuery.data ?? []).length === 0 ? <p className="text-sm text-slate-500">No automation runs have been recorded yet.</p> : <div className="overflow-x-auto"><table className="w-full min-w-[640px] text-left text-xs"><thead className="text-[10px] uppercase tracking-wide text-slate-400"><tr><th className="py-2">Event</th><th>Subject</th><th>Status</th><th>Recipients</th><th>Attempts</th><th>Processed</th></tr></thead><tbody>{logsQuery.data?.map((log) => <tr key={log.id} className="border-t border-slate-100"><td className="py-3 font-medium text-slate-700">{log.event_type}</td><td>{log.subject_type}</td><td><span className="rounded-full bg-slate-100 px-2 py-1 capitalize">{log.status}</span></td><td>{log.recipient_count}</td><td>{log.attempt_count}</td><td>{log.processed_at ? new Date(log.processed_at).toLocaleString() : 'Pending retry'}</td></tr>)}</tbody></table></div>}</CardContent></Card>}
  </div>
}
