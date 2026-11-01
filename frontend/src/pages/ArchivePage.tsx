import { useState } from 'react'
import type { ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Archive, History, RotateCcw, Search } from 'lucide-react'
import { useOutletContext } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { archiveRecord, getArchive, getArchiveEligible, getArchiveHistory, restoreRecord } from '@/features/archive/api'
import type { ArchiveRecord } from '@/features/archive/api'
import type { AppShellOutletContext } from '@/components/layout/AppShell'

const label = (value: string) => value.replaceAll('_', ' ')
const dateLabel = (value: string | null) => value ? new Date(value).toLocaleString() : '—'

export function ArchivePage() {
  const { selectedOrganizationId, selectedOrganization } = useOutletContext<AppShellOutletContext>()
  const [search, setSearch] = useState('')
  const [recordType, setRecordType] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [historyRecord, setHistoryRecord] = useState<ArchiveRecord | null>(null)
  const queryClient = useQueryClient()
  const canManageArchive = ['organization_owner', 'administrator'].includes(selectedOrganization?.role ?? '')
  const archiveQuery = useQuery({ queryKey: ['archive', selectedOrganizationId, search, recordType, startDate, endDate], queryFn: () => getArchive(selectedOrganizationId, search, recordType, startDate, endDate), enabled: Boolean(selectedOrganizationId), retry: false })
  const eligibleQuery = useQuery({ queryKey: ['archive', 'eligible', selectedOrganizationId, search, recordType], queryFn: () => getArchiveEligible(selectedOrganizationId, search, recordType), enabled: Boolean(selectedOrganizationId && canManageArchive), retry: false })
  const historyQuery = useQuery({ queryKey: ['archive', 'history', selectedOrganizationId, historyRecord?.record_type, historyRecord?.record_id], queryFn: () => getArchiveHistory(selectedOrganizationId, historyRecord!.record_type, historyRecord!.record_id), enabled: Boolean(historyRecord), retry: false })
  const archiveMutation = useMutation({
    mutationFn: ({ record, reason }: { record: ArchiveRecord; reason: string }) => archiveRecord(selectedOrganizationId, record, reason),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ['archive'] }); void queryClient.invalidateQueries({ queryKey: ['reports'] }); void queryClient.invalidateQueries({ queryKey: ['imports'] }); void queryClient.invalidateQueries({ queryKey: ['exports'] }) },
  })
  const restoreMutation = useMutation({
    mutationFn: ({ record, reason }: { record: ArchiveRecord; reason: string }) => restoreRecord(selectedOrganizationId, record, reason),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ['archive'] }); void queryClient.invalidateQueries({ queryKey: ['reports'] }); void queryClient.invalidateQueries({ queryKey: ['imports'] }); void queryClient.invalidateQueries({ queryKey: ['exports'] }) },
  })

  function onArchive(record: ArchiveRecord) {
    const reason = window.prompt(`Archive ${record.reference}. Enter an archive reason:`)?.trim()
    if (reason && reason.length >= 3) archiveMutation.mutate({ record, reason })
  }
  function onRestore(record: ArchiveRecord) {
    const reason = window.prompt(`Restore ${record.reference}. Enter a reason for restoring:`)?.trim()
    if (reason && reason.length >= 3) restoreMutation.mutate({ record, reason })
  }

  const mutationError = archiveMutation.error ?? restoreMutation.error

  if (!selectedOrganizationId) return <div className="rounded-xl border border-dashed bg-white p-10 text-center text-sm text-slate-500">Select an organization to view archive records.</div>
  return (
    <div className="space-y-6">
      <div className="space-y-3"><div><p className="text-xs font-bold uppercase tracking-[0.18em] text-sky-700">Historical records</p><h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">Archive</h1><p className="mt-1 text-sm text-slate-500">Archive finalized orders without deleting their documents, invoices, payments, or audit history.</p></div><div className="flex flex-wrap items-end gap-2 rounded-xl border border-slate-200 bg-white p-3"><div className="relative min-w-[220px] flex-1"><Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={15} /><input aria-label="Search archive" className="w-full rounded-lg border border-slate-200 py-2.5 pl-9 pr-3 text-sm outline-none focus:border-sky-400" placeholder="Search reference or partner" value={search} onChange={(event) => setSearch(event.target.value)} /></div><label className="text-xs font-semibold text-slate-600">Record type<select aria-label="Archive record type" className="mt-1 block rounded-lg border border-slate-200 bg-white px-2 py-2.5 text-sm" value={recordType} onChange={(event) => setRecordType(event.target.value)}><option value="">All records</option><option value="import_order">Import orders</option><option value="export_order">Export orders</option></select></label><label className="text-xs font-semibold text-slate-600">Archived from<input aria-label="Archived from date" type="date" className="mt-1 block rounded-lg border border-slate-200 px-2 py-2 text-sm" value={startDate} max={endDate || undefined} onChange={(event) => setStartDate(event.target.value)} /></label><label className="text-xs font-semibold text-slate-600">Archived to<input aria-label="Archived to date" type="date" className="mt-1 block rounded-lg border border-slate-200 px-2 py-2 text-sm" value={endDate} min={startDate || undefined} onChange={(event) => setEndDate(event.target.value)} /></label></div></div>
      {(archiveMutation.isError || restoreMutation.isError) && <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{mutationError instanceof Error ? mutationError.message : 'Archive action failed.'}</div>}
      {canManageArchive && <Card><CardHeader><CardTitle className="flex items-center gap-2 text-base"><Archive size={17} />Eligible orders</CardTitle><CardDescription>Only received imports and delivered exports, plus cancelled orders, can be archived.</CardDescription></CardHeader><CardContent><RecordTable records={eligibleQuery.data?.items ?? []} loading={eligibleQuery.isPending} error={eligibleQuery.error} empty="No completed or cancelled orders are currently eligible." actionLabel="Archive" onAction={onArchive} actionIcon={<Archive size={14} />} /></CardContent></Card>}
      <Card><CardHeader><CardTitle className="flex items-center gap-2 text-base"><History size={17} />Archived records</CardTitle><CardDescription>{archiveQuery.data?.total ?? 0} records retained in this organization.</CardDescription></CardHeader><CardContent><RecordTable records={archiveQuery.data?.items ?? []} loading={archiveQuery.isPending} error={archiveQuery.error} empty="No records have been archived yet." actionLabel={canManageArchive ? 'Restore' : undefined} onAction={onRestore} actionIcon={<RotateCcw size={14} />} onHistory={setHistoryRecord} /></CardContent></Card>
      {historyRecord && <Card><CardHeader className="flex flex-row items-center justify-between"><div><CardTitle className="text-base">Archive history · {historyRecord.reference}</CardTitle><CardDescription>Archive and restore actions are retained as an audit trail.</CardDescription></div><Button size="sm" variant="outline" onClick={() => setHistoryRecord(null)}>Close</Button></CardHeader><CardContent>{historyQuery.isPending ? <p className="text-sm text-slate-500">Loading history…</p> : historyQuery.isError ? <p role="alert" className="text-sm text-rose-600">Could not load archive history.</p> : (historyQuery.data ?? []).length === 0 ? <p className="text-sm text-slate-400">No archive events found.</p> : <ol className="space-y-3 border-l border-slate-200 pl-4">{historyQuery.data?.map((event) => <li key={event.id} className="relative"><span className="absolute -left-[21px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-white bg-sky-500 ring-1 ring-sky-200" /><div className="flex flex-wrap items-center justify-between gap-2"><p className="text-sm font-semibold capitalize text-slate-800">{label(event.action)}</p><time className="text-xs text-slate-400">{dateLabel(event.created_at)}</time></div><p className="mt-1 text-sm text-slate-600">{event.reason}</p></li>)}</ol>}</CardContent></Card>}
      <p className="text-xs text-slate-400">Archived business records remain available to authorized users. Restoring an order returns it to the operational register in its previous business status; no financial or inventory entries are rewritten.</p>
    </div>
  )
}

function RecordTable({ records, loading, error, empty, actionLabel, actionIcon, onAction, onHistory }: { records: ArchiveRecord[]; loading: boolean; error: unknown; empty: string; actionLabel?: string; actionIcon?: ReactNode; onAction?: (record: ArchiveRecord) => void; onHistory?: (record: ArchiveRecord) => void }) {
  if (loading) return <div className="space-y-3 py-4"><div className="h-4 w-2/3 animate-pulse rounded bg-slate-100" /><div className="h-4 w-full animate-pulse rounded bg-slate-100" /></div>
  if (error) return <p role="alert" className="py-5 text-sm text-rose-600">{error instanceof Error ? error.message : 'Could not load records.'}</p>
  if (!records.length) return <div className="rounded-xl border border-dashed border-slate-200 py-8 text-center text-sm text-slate-400">{empty}</div>
  return <div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-sm"><thead className="border-b border-slate-100 text-[11px] uppercase tracking-wide text-slate-400"><tr><th className="py-2">Reference</th><th>Type / Partner</th><th>Status</th><th>Date</th><th>Reason</th><th className="text-right">Actions</th></tr></thead><tbody className="divide-y divide-slate-100">{records.map((record) => <tr key={`${record.record_type}-${record.record_id}`}><td className="py-3 font-semibold text-slate-800">{record.reference}</td><td><span className="block capitalize text-slate-700">{label(record.record_type)}</span><span className="text-xs text-slate-400">{record.partner_name}</span></td><td><span className="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-semibold capitalize text-slate-600">{label(record.status)}</span></td><td className="text-xs text-slate-500">{dateLabel(record.archived_at || record.created_at)}</td><td className="max-w-[220px] truncate text-xs text-slate-500">{record.archive_reason || '—'}</td><td><div className="flex justify-end gap-2">{onHistory && <Button variant="outline" size="sm" onClick={() => onHistory(record)}><History size={13} /></Button>}{actionLabel && onAction && <Button variant="outline" size="sm" onClick={() => onAction(record)}>{actionIcon}{actionLabel}</Button>}</div></td></tr>)}</tbody></table></div>
}
