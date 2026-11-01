import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, CalendarClock, CheckCircle2, Clock3, MapPin, PackageCheck, RefreshCw, Ship, Truck } from 'lucide-react'
import { useOutletContext } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import type { AppShellOutletContext } from '@/components/layout/AppShell'
import { createShipmentMilestone, listShipmentMilestones, listShipments, updateShipment } from '@/features/shipments/api'
import type { Shipment } from '@/features/shipments/types'

const inputClass = 'w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100'
const statusClass: Record<string, string> = {
  planned: 'bg-slate-100 text-slate-700', in_transit: 'bg-sky-100 text-sky-800', arrived: 'bg-indigo-100 text-indigo-800',
  delayed: 'bg-rose-100 text-rose-800', delivered: 'bg-emerald-100 text-emerald-800', cancelled: 'bg-slate-100 text-slate-500',
}
const dateLabel = (value: string | null) => value ? new Date(`${value.slice(0, 10)}T12:00:00`).toLocaleDateString() : '—'
const dateTimeLabel = (value: string) => new Date(value).toLocaleString()

export function ShipmentsPage() {
  const { selectedOrganizationId, selectedOrganization } = useOutletContext<AppShellOutletContext>()
  const queryClient = useQueryClient()
  const [typeFilter, setTypeFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [search, setSearch] = useState('')
  const [selectedKey, setSelectedKey] = useState('')
  const [delayReason, setDelayReason] = useState('')
  const [milestoneName, setMilestoneName] = useState('')
  const [milestoneDescription, setMilestoneDescription] = useState('')
  const [milestoneTime, setMilestoneTime] = useState(() => new Date().toISOString().slice(0, 16))
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const canUpdate = ['organization_owner', 'administrator', 'import_manager', 'export_manager', 'operations_staff'].includes(selectedOrganization?.role ?? '')

  const shipmentsQuery = useQuery({
    queryKey: ['shipments', selectedOrganizationId, typeFilter, statusFilter, search],
    queryFn: () => listShipments(selectedOrganizationId, typeFilter, statusFilter, search),
    enabled: Boolean(selectedOrganizationId),
  })
  const shipments = shipmentsQuery.data ?? []
  const selectedShipment = shipments.find((shipment) => `${shipment.shipment_type}:${shipment.id}` === selectedKey) ?? shipments[0] ?? null
  const milestonesQuery = useQuery({
    queryKey: ['shipments', selectedOrganizationId, selectedShipment?.shipment_type, selectedShipment?.id, 'milestones'],
    queryFn: () => listShipmentMilestones(selectedOrganizationId, selectedShipment!.shipment_type, selectedShipment!.id),
    enabled: Boolean(selectedOrganizationId && selectedShipment),
  })

  const updateMutation = useMutation({
    mutationFn: ({ shipment, payload }: { shipment: Shipment; payload: Record<string, unknown> }) => updateShipment(selectedOrganizationId, shipment.shipment_type, shipment.id, payload),
    onSuccess: () => { setError(''); setNotice('Shipment tracking details were updated.'); queryClient.invalidateQueries({ queryKey: ['shipments', selectedOrganizationId] }) },
    onError: (err) => { setNotice(''); setError(err instanceof Error ? err.message : 'Shipment update failed.') },
  })
  const milestoneMutation = useMutation({
    mutationFn: () => {
      if (!selectedShipment) throw new Error('Select a shipment first.')
      return createShipmentMilestone(selectedOrganizationId, selectedShipment.shipment_type, selectedShipment.id, {
        name: milestoneName, description: milestoneDescription || null, occurred_at: new Date(milestoneTime).toISOString(),
      })
    },
    onSuccess: () => {
      setMilestoneName(''); setMilestoneDescription(''); setNotice('Shipment milestone added.'); setError('')
      queryClient.invalidateQueries({ queryKey: ['shipments', selectedOrganizationId, selectedShipment?.shipment_type, selectedShipment?.id, 'milestones'] })
    },
    onError: (err) => { setNotice(''); setError(err instanceof Error ? err.message : 'Milestone could not be added.') },
  })

  const delayedCount = useMemo(() => shipments.filter((shipment) => shipment.status === 'delayed').length, [shipments])
  const activeCount = useMemo(() => shipments.filter((shipment) => ['planned', 'in_transit'].includes(shipment.status)).length, [shipments])

  function updateStatus(shipment: Shipment, status: 'in_transit' | 'delayed') {
    const payload: Record<string, unknown> = { status }
    if (status === 'delayed') payload.delay_reason = delayReason.trim()
    updateMutation.mutate({ shipment, payload })
  }

  return <div className="space-y-6">
    <section className="rounded-2xl bg-[#122338] px-5 py-6 text-white shadow-lg shadow-slate-900/10 sm:px-7">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div><div className="mb-2 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/[0.07] px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-sky-200"><Ship size={13} /> Logistics control</div><h2 className="text-2xl font-bold tracking-tight">Shipment tracking</h2><p className="mt-2 max-w-xl text-sm leading-6 text-slate-300">Monitor import and export shipments together. Tracking events are manually recorded; live carrier integrations are not enabled.</p></div>
        <Button variant="outline" className="border-white/20 bg-white/[0.08] text-white hover:bg-white/[0.14] hover:text-white" onClick={() => shipmentsQuery.refetch()} disabled={shipmentsQuery.isFetching}><RefreshCw size={14} className={shipmentsQuery.isFetching ? 'animate-spin' : ''} />Refresh</Button>
      </div>
    </section>

    <section className="grid gap-3 sm:grid-cols-3">
      <Card className="rounded-xl"><CardContent className="flex items-center gap-3 p-4"><span className="rounded-lg bg-sky-50 p-2.5 text-sky-700"><Truck size={18} /></span><div><p className="text-xs text-slate-500">Active shipments</p><p className="text-2xl font-bold">{activeCount}</p></div></CardContent></Card>
      <Card className="rounded-xl"><CardContent className="flex items-center gap-3 p-4"><span className="rounded-lg bg-rose-50 p-2.5 text-rose-700"><AlertTriangle size={18} /></span><div><p className="text-xs text-slate-500">Delayed shipments</p><p className="text-2xl font-bold">{delayedCount}</p></div></CardContent></Card>
      <Card className="rounded-xl"><CardContent className="flex items-center gap-3 p-4"><span className="rounded-lg bg-emerald-50 p-2.5 text-emerald-700"><CheckCircle2 size={18} /></span><div><p className="text-xs text-slate-500">Total shipments</p><p className="text-2xl font-bold">{shipments.length}</p></div></CardContent></Card>
    </section>

    {notice && <p role="status" className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{notice}</p>}
    {error && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</p>}

    <section className="grid items-start gap-5 xl:grid-cols-[minmax(0,1.15fr)_minmax(360px,0.85fr)]">
      <Card className="rounded-2xl border-slate-200/80 shadow-sm">
        <CardHeader className="border-b border-slate-100"><CardTitle className="text-base">Shipment register</CardTitle><CardDescription>Filter by trade direction, status, carrier, or tracking reference.</CardDescription></CardHeader>
        <CardContent className="space-y-4 p-4 sm:p-5">
          <div className="grid gap-2 sm:grid-cols-3">
            <select className={inputClass} value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)} aria-label="Filter shipment type"><option value="all">All directions</option><option value="import">Imports</option><option value="export">Exports</option></select>
            <select className={inputClass} value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} aria-label="Filter shipment status"><option value="all">All statuses</option>{['planned', 'in_transit', 'arrived', 'delayed', 'delivered', 'cancelled'].map((status) => <option key={status} value={status}>{status.replace('_', ' ')}</option>)}</select>
            <input className={inputClass} value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search shipment…" aria-label="Search shipment" />
          </div>
          {shipmentsQuery.isPending ? <p className="py-8 text-center text-sm text-slate-500">Loading shipments…</p> : null}
          {shipmentsQuery.isError ? <div className="rounded-lg bg-rose-50 p-4 text-sm text-rose-800">{shipmentsQuery.error instanceof Error ? shipmentsQuery.error.message : 'Shipments could not be loaded.'}</div> : null}
          {!shipmentsQuery.isPending && !shipmentsQuery.isError && shipments.length === 0 ? <div className="rounded-xl border border-dashed border-slate-300 px-5 py-10 text-center"><Ship className="mx-auto text-slate-300" size={28} /><p className="mt-3 text-sm font-semibold text-slate-700">No shipments found</p><p className="mt-1 text-xs text-slate-500">Create a shipment from an approved import or export order.</p></div> : null}
          <div className="space-y-2">
            {shipments.map((shipment) => {
              const key = `${shipment.shipment_type}:${shipment.id}`
              const active = (selectedShipment?.id === shipment.id && selectedShipment?.shipment_type === shipment.shipment_type)
              return <button type="button" key={key} onClick={() => setSelectedKey(key)} className={`w-full rounded-xl border p-4 text-left transition ${active ? 'border-sky-300 bg-sky-50/70 ring-1 ring-sky-100' : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'}`}>
                <div className="flex flex-wrap items-start justify-between gap-2"><div><div className="flex items-center gap-2"><span className="text-sm font-bold text-slate-900">{shipment.shipment_reference}</span><span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${statusClass[shipment.status] ?? 'bg-slate-100 text-slate-700'}`}>{shipment.status.replace('_', ' ')}</span></div><p className="mt-1 text-xs text-slate-500">{shipment.shipment_type.toUpperCase()} · Order {shipment.order_reference}</p></div><span className="rounded-md bg-slate-100 px-2 py-1 text-[10px] font-bold text-slate-600">{shipment.transport_mode.toUpperCase()}</span></div>
                <div className="mt-3 grid gap-2 text-xs text-slate-500 sm:grid-cols-3"><span className="flex items-center gap-1.5"><Truck size={13} />{shipment.carrier || 'Carrier not set'}</span><span className="flex items-center gap-1.5"><MapPin size={13} />{shipment.origin || 'Origin'} → {shipment.destination || 'Destination'}</span><span className="flex items-center gap-1.5"><CalendarClock size={13} />ETA {dateLabel(shipment.estimated_arrival)}</span></div>
              </button>
            })}
          </div>
        </CardContent>
      </Card>

      <Card className="rounded-2xl border-slate-200/80 shadow-sm">
        <CardHeader className="border-b border-slate-100"><CardTitle className="text-base">Shipment timeline</CardTitle><CardDescription>{selectedShipment ? `${selectedShipment.shipment_reference} · ${selectedShipment.shipment_type} order ${selectedShipment.order_reference}` : 'Select a shipment to inspect its timeline.'}</CardDescription></CardHeader>
        <CardContent className="space-y-5 p-4 sm:p-5">
          {selectedShipment ? <>
            <div className="grid grid-cols-2 gap-3 text-xs"><div className="rounded-lg bg-slate-50 p-3"><p className="text-slate-500">Departure</p><p className="mt-1 font-semibold text-slate-800">{dateLabel(selectedShipment.actual_departure || selectedShipment.estimated_departure)}</p></div><div className="rounded-lg bg-slate-50 p-3"><p className="text-slate-500">Arrival</p><p className="mt-1 font-semibold text-slate-800">{dateLabel(selectedShipment.actual_arrival || selectedShipment.estimated_arrival)}</p></div></div>
            {selectedShipment.tracking_reference && <p className="text-xs text-slate-600">Tracking reference: <strong>{selectedShipment.tracking_reference}</strong></p>}
            {selectedShipment.delay_reason && <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800"><strong>Delay reason:</strong> {selectedShipment.delay_reason}</div>}
            {canUpdate && selectedShipment.status !== 'delivered' && selectedShipment.status !== 'cancelled' && <div className="space-y-2 rounded-xl border border-slate-200 p-3"><p className="text-xs font-bold text-slate-700">Update status</p><div className="flex flex-wrap gap-2">{selectedShipment.status !== 'in_transit' && <Button size="sm" variant="outline" onClick={() => updateStatus(selectedShipment, 'in_transit')} disabled={updateMutation.isPending}>Resume / mark in transit</Button>}{selectedShipment.status !== 'delayed' && <Button size="sm" variant="outline" className="border-rose-200 text-rose-700 hover:bg-rose-50" onClick={() => updateStatus(selectedShipment, 'delayed')} disabled={updateMutation.isPending || !delayReason.trim()}>Mark delayed</Button>}</div>{selectedShipment.status !== 'delayed' && <input className={inputClass} value={delayReason} onChange={(event) => setDelayReason(event.target.value)} placeholder="Delay reason (required to mark delayed)" aria-label="Delay reason" />}</div>}
            <div><div className="mb-3 flex items-center justify-between"><h3 className="text-xs font-bold uppercase tracking-wide text-slate-600">Recorded events</h3><span className="text-[10px] text-slate-400">Manual updates</span></div>{milestonesQuery.isPending ? <p className="text-xs text-slate-500">Loading timeline…</p> : milestonesQuery.isError ? <p className="text-xs text-rose-700">Timeline could not be loaded.</p> : (milestonesQuery.data ?? []).length === 0 ? <p className="text-xs text-slate-500">No manual milestone events have been recorded.</p> : <ol className="space-y-3 border-l border-slate-200 pl-4">{milestonesQuery.data?.map((milestone) => <li key={milestone.id} className="relative"><span className="absolute -left-[21px] top-1 h-2.5 w-2.5 rounded-full border-2 border-white bg-sky-500 ring-1 ring-sky-200" /><p className="text-xs font-semibold text-slate-800">{milestone.name}</p><p className="mt-0.5 text-[11px] text-slate-500">{dateTimeLabel(milestone.occurred_at)}{milestone.description ? ` · ${milestone.description}` : ''}</p></li>)}</ol>}</div>
            {canUpdate && <form className="space-y-2 border-t border-slate-100 pt-4" onSubmit={(event) => { event.preventDefault(); milestoneMutation.mutate() }}><h3 className="text-xs font-bold text-slate-700">Add milestone</h3><input className={inputClass} value={milestoneName} onChange={(event) => setMilestoneName(event.target.value)} placeholder="Milestone name" required minLength={2} /><textarea className={inputClass} rows={2} value={milestoneDescription} onChange={(event) => setMilestoneDescription(event.target.value)} placeholder="Description (optional)" /><input className={inputClass} type="datetime-local" value={milestoneTime} onChange={(event) => setMilestoneTime(event.target.value)} required /><Button size="sm" type="submit" disabled={milestoneMutation.isPending || !milestoneName.trim()}><PackageCheck size={14} />Add timeline event</Button></form>}
          </> : <div className="py-10 text-center text-sm text-slate-500"><Clock3 className="mx-auto mb-3 text-slate-300" size={28} />Select a shipment from the register.</div>}
        </CardContent>
      </Card>
    </section>
  </div>
}
