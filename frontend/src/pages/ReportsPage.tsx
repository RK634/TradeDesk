import { useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Activity, AlertTriangle, ArrowDownToLine, FileWarning, Ship, TrendingDown, TrendingUp } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { downloadReportCsv, getImportCostReport, getInventoryReport, getMissingDocumentsReport, getOrderReport, getPartnerReport, getReportSummary, getShipmentPerformanceReport } from '@/features/reports/api'
import type { AppShellOutletContext } from '@/components/layout/AppShell'
import { useOutletContext } from 'react-router-dom'

function dateValue(date: Date) { return date.toISOString().slice(0, 10) }
function money(value: string, currency: string) {
  const amount = Number(value)
  return new Intl.NumberFormat(undefined, { style: 'currency', currency, maximumFractionDigits: 2 }).format(Number.isFinite(amount) ? amount : 0)
}

export function ReportsPage() {
  const { selectedOrganizationId, selectedOrganization } = useOutletContext<AppShellOutletContext>()
  const [endDate, setEndDate] = useState(dateValue(new Date()))
  const [startDate, setStartDate] = useState(() => { const date = new Date(); date.setDate(date.getDate() - 29); return dateValue(date) })
  const [lowStockOnly, setLowStockOnly] = useState(false)
  const [downloadError, setDownloadError] = useState('')
  const canViewFinancial = ['organization_owner', 'administrator', 'finance_staff'].includes(selectedOrganization?.role ?? '')
  const canExportReports = ['organization_owner', 'administrator', 'finance_staff'].includes(selectedOrganization?.role ?? '')
  const summaryQuery = useQuery({ queryKey: ['reports', 'summary', selectedOrganizationId, startDate, endDate], queryFn: () => getReportSummary(selectedOrganizationId, startDate, endDate), enabled: Boolean(selectedOrganizationId), retry: false })
  const ordersQuery = useQuery({ queryKey: ['reports', 'orders', selectedOrganizationId, startDate, endDate], queryFn: () => getOrderReport(selectedOrganizationId, startDate, endDate), enabled: Boolean(selectedOrganizationId), retry: false })
  const inventoryQuery = useQuery({ queryKey: ['reports', 'inventory', selectedOrganizationId, lowStockOnly], queryFn: () => getInventoryReport(selectedOrganizationId, lowStockOnly), enabled: Boolean(selectedOrganizationId), retry: false })
  const importCostsQuery = useQuery({ queryKey: ['reports', 'import-costs', selectedOrganizationId, startDate, endDate], queryFn: () => getImportCostReport(selectedOrganizationId, startDate, endDate), enabled: Boolean(selectedOrganizationId), retry: false })
  const partnersQuery = useQuery({ queryKey: ['reports', 'partners', selectedOrganizationId, startDate, endDate], queryFn: () => getPartnerReport(selectedOrganizationId, startDate, endDate), enabled: Boolean(selectedOrganizationId), retry: false })
  const shipmentsQuery = useQuery({ queryKey: ['reports', 'shipment-performance', selectedOrganizationId, startDate, endDate], queryFn: () => getShipmentPerformanceReport(selectedOrganizationId, startDate, endDate), enabled: Boolean(selectedOrganizationId), retry: false })
  const missingDocumentsQuery = useQuery({ queryKey: ['reports', 'missing-documents', selectedOrganizationId], queryFn: () => getMissingDocumentsReport(selectedOrganizationId), enabled: Boolean(selectedOrganizationId), retry: false })
  const currencies = summaryQuery.data?.financial ?? []
  const orderRows = ordersQuery.data ?? []
  const statusSummary = useMemo(() => [
    ...(summaryQuery.data?.imports.by_status.map((row) => ({ ...row, direction: 'Import' })) ?? []),
    ...(summaryQuery.data?.exports.by_status.map((row) => ({ ...row, direction: 'Export' })) ?? []),
  ], [summaryQuery.data])

  async function exportCsv(type: string) {
    setDownloadError('')
    try { await downloadReportCsv(selectedOrganizationId, type, startDate, endDate) }
    catch (error) { setDownloadError(error instanceof Error ? error.message : 'CSV export failed.') }
  }

  if (!selectedOrganizationId) return <div className="rounded-xl border border-dashed bg-white p-10 text-center text-sm text-slate-500">Select an organization to view reports.</div>

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 xl:flex-row xl:items-end">
        <div><p className="text-xs font-bold uppercase tracking-[0.18em] text-sky-700">Business intelligence</p><h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">Reports & analytics</h1><p className="mt-1 text-sm text-slate-500">Operational performance, stock health, shipment activity, and currency-separated financial positions.</p></div>
        <div className="flex flex-wrap items-end gap-2 rounded-xl border border-slate-200 bg-white p-3">
          <label className="text-xs font-semibold text-slate-600">From<input aria-label="Report start date" type="date" className="mt-1 block rounded-lg border border-slate-200 px-2 py-2 text-sm" value={startDate} max={endDate} onChange={(event) => setStartDate(event.target.value)} /></label>
          <label className="text-xs font-semibold text-slate-600">To<input aria-label="Report end date" type="date" className="mt-1 block rounded-lg border border-slate-200 px-2 py-2 text-sm" value={endDate} min={startDate} onChange={(event) => setEndDate(event.target.value)} /></label>
          <Button variant="outline" onClick={() => void summaryQuery.refetch()} disabled={summaryQuery.isFetching}>Refresh</Button>
        </div>
      </div>

      {downloadError && <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{downloadError}</div>}
      {summaryQuery.isError && <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{summaryQuery.error instanceof Error ? summaryQuery.error.message : 'Reports could not be loaded.'}</div>}

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric title="Import orders" value={summaryQuery.data?.imports.total ?? '—'} icon={<TrendingDown size={18} />} detail="Created in selected period" />
        <Metric title="Export orders" value={summaryQuery.data?.exports.total ?? '—'} icon={<TrendingUp size={18} />} detail="Created in selected period" />
        <Metric title="Shipments" value={summaryQuery.data?.shipments.total ?? '—'} icon={<Ship size={18} />} detail={`${summaryQuery.data?.shipments.delayed ?? 0} delayed`} warning={(summaryQuery.data?.shipments.delayed ?? 0) > 0} />
        <Metric title="Low-stock balances" value={summaryQuery.data?.inventory.low_stock_rows ?? '—'} icon={<AlertTriangle size={18} />} detail={`${summaryQuery.data?.inventory.balance_rows ?? 0} stock/location balances`} warning={(summaryQuery.data?.inventory.low_stock_rows ?? 0) > 0} />
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <Card>
          <CardHeader><CardTitle className="text-base">Order status distribution</CardTitle><CardDescription>Only non-archived orders are included in operational reports.</CardDescription></CardHeader>
          <CardContent>
            {summaryQuery.isPending ? <Loading /> : statusSummary.length === 0 ? <Empty text="No orders were recorded in this period." /> : <div className="space-y-3">{statusSummary.map((row) => <div key={`${row.direction}-${row.status}`} className="flex items-center gap-3"><span className="w-16 text-xs font-semibold text-slate-500">{row.direction}</span><span className="min-w-0 flex-1 truncate text-sm text-slate-700">{row.status.replaceAll('_', ' ')}</span><div className="h-2 w-28 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-sky-600" style={{ width: `${Math.min(100, row.count / Math.max(1, statusSummary.reduce((sum, item) => sum + item.count, 0)) * 100)}%` }} /></div><span className="w-8 text-right text-sm font-semibold tabular-nums text-slate-800">{row.count}</span></div>)}</div>}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-base">Financial position by currency</CardTitle><CardDescription>Outstanding balances are not combined across currencies.</CardDescription></CardHeader>
          <CardContent>
            {!canViewFinancial ? <Empty text="Your role does not have financial report access." /> : summaryQuery.isPending ? <Loading /> : currencies.length === 0 ? <Empty text="No outstanding financial balances were found for this period." /> : <div className="space-y-3">{currencies.map((row) => <div key={row.currency} className="rounded-xl border border-slate-100 p-3"><div className="mb-2 text-sm font-bold text-slate-800">{row.currency}</div><div className="grid grid-cols-2 gap-3 text-xs"><Balance label="Receivables" value={money(row.receivables_outstanding, row.currency)} /><Balance label="Payables" value={money(row.payables_outstanding, row.currency)} /><Balance label="Overdue receivables" value={money(row.overdue_receivables, row.currency)} danger={Number(row.overdue_receivables) > 0} /><Balance label="Overdue payables" value={money(row.overdue_payables, row.currency)} danger={Number(row.overdue_payables) > 0} /></div></div>)}</div>}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3"><div><CardTitle className="text-base">Inventory position</CardTitle><CardDescription>On-hand, reserved, and available quantities by product and location.</CardDescription></div><label className="flex items-center gap-2 text-xs font-semibold text-slate-600"><input type="checkbox" checked={lowStockOnly} onChange={(event) => setLowStockOnly(event.target.checked)} />Low stock only</label></CardHeader>
        <CardContent>
          {canExportReports && <div className="mb-3 flex flex-wrap gap-2"><Button size="sm" variant="outline" onClick={() => void exportCsv('inventory')}><ArrowDownToLine size={14} className="mr-2" />Export stock CSV</Button><Button size="sm" variant="outline" onClick={() => void exportCsv('inventory_movements')}><ArrowDownToLine size={14} className="mr-2" />Export movements CSV</Button></div>}
          {inventoryQuery.isPending ? <Loading /> : inventoryQuery.isError ? <div role="alert" className="text-sm text-rose-600">Could not load inventory report.</div> : (inventoryQuery.data ?? []).length === 0 ? <Empty text="No inventory balances match this filter." /> : <div className="overflow-x-auto"><table className="w-full min-w-[720px] text-left text-sm"><thead className="border-b border-slate-100 text-[11px] uppercase tracking-wide text-slate-400"><tr><th className="py-2">Product</th><th>Location</th><th className="text-right">On hand</th><th className="text-right">Reserved</th><th className="text-right">Available</th><th className="text-right">Status</th></tr></thead><tbody className="divide-y divide-slate-100">{inventoryQuery.data?.map((row) => <tr key={`${row.product_id}-${row.location_id}`}><td className="py-3"><div className="font-semibold text-slate-800">{row.product_name}</div><div className="text-xs text-slate-400">{row.sku}</div></td><td className="text-slate-600">{row.location_name} · {row.location_code}</td><td className="text-right tabular-nums">{row.quantity_on_hand}</td><td className="text-right tabular-nums">{row.reserved_quantity}</td><td className="text-right font-semibold tabular-nums">{row.available_quantity}</td><td className="text-right"><span className={`rounded-full px-2 py-1 text-[10px] font-bold ${row.is_low_stock ? 'bg-amber-50 text-amber-700' : 'bg-emerald-50 text-emerald-700'}`}>{row.is_low_stock ? 'Low stock' : 'Healthy'}</span></td></tr>)}</tbody></table></div>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-3"><div><CardTitle className="text-base">Order register</CardTitle><CardDescription>{orderRows.length} orders in the selected period.</CardDescription></div>{canExportReports && <Button size="sm" variant="outline" onClick={() => void exportCsv('orders')}><ArrowDownToLine size={14} className="mr-2" />Export orders CSV</Button>}</CardHeader>
        <CardContent>
          {ordersQuery.isPending ? <Loading /> : orderRows.length === 0 ? <Empty text="No import or export orders were recorded in this period." /> : <div className="overflow-x-auto"><table className="w-full min-w-[700px] text-left text-sm"><thead className="border-b border-slate-100 text-[11px] uppercase tracking-wide text-slate-400"><tr><th className="py-2">Reference</th><th>Direction</th><th>Partner</th><th>Status</th><th className="text-right">Total</th></tr></thead><tbody className="divide-y divide-slate-100">{orderRows.slice(0, 100).map((row) => <tr key={`${row.direction}-${row.record_id}`}><td className="py-3 font-semibold text-slate-800">{row.reference}</td><td className="capitalize text-slate-600">{row.direction}</td><td className="text-slate-600">{row.partner_name}</td><td><span className="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-semibold text-slate-600">{row.status.replaceAll('_', ' ')}</span></td><td className="text-right tabular-nums">{money(row.order_total, row.currency)}</td></tr>)}</tbody></table></div>}
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3"><div><CardTitle className="text-base">Import cost variance</CardTitle><CardDescription>Estimated landed cost compared with recorded actual freight, insurance, duties, and other costs. Values stay in each order currency.</CardDescription></div>{canExportReports && <Button size="sm" variant="outline" onClick={() => void exportCsv('import_costs')}><ArrowDownToLine size={14} className="mr-2" />Export CSV</Button>}</CardHeader>
        <CardContent>{importCostsQuery.isPending ? <Loading /> : importCostsQuery.isError ? <p role="alert" className="text-sm text-rose-600">Could not load import cost report.</p> : (importCostsQuery.data ?? []).length === 0 ? <Empty text="No import cost records were found in this period." /> : <div className="overflow-x-auto"><table className="w-full min-w-[900px] text-left text-sm"><thead className="border-b border-slate-100 text-[11px] uppercase tracking-wide text-slate-400"><tr><th className="py-2">Import reference</th><th>Supplier</th><th>Currency</th><th className="text-right">Estimated total</th><th className="text-right">Actual total</th><th className="text-right">Variance</th></tr></thead><tbody className="divide-y divide-slate-100">{importCostsQuery.data?.map((row) => <tr key={row.record_id}><td className="py-3 font-semibold text-slate-800">{row.reference}</td><td className="text-slate-600">{row.supplier_name}</td><td>{row.currency}</td><td className="text-right tabular-nums">{money(row.estimated_total, row.currency)}</td><td className="text-right tabular-nums">{money(row.actual_total, row.currency)}</td><td className={`text-right font-semibold tabular-nums ${Number(row.variance) > 0 ? 'text-rose-600' : 'text-emerald-700'}`}>{money(row.variance, row.currency)}</td></tr>)}</tbody></table></div>}</CardContent>
      </Card>

      <div className="grid gap-5 xl:grid-cols-2">
        <Card><CardHeader className="flex flex-row items-center justify-between gap-2"><div><CardTitle className="text-base">Customer and supplier summary</CardTitle><CardDescription>Order totals grouped by partner, direction, and currency.</CardDescription></div>{canExportReports && <Button size="sm" variant="outline" onClick={() => void exportCsv('partners')}><ArrowDownToLine size={14} className="mr-2" />CSV</Button>}</CardHeader><CardContent>{partnersQuery.isPending ? <Loading /> : (partnersQuery.data ?? []).length === 0 ? <Empty text="No partner order totals for this period." /> : <div className="space-y-2">{partnersQuery.data?.map((row) => <div key={`${row.direction}-${row.partner_name}-${row.currency}`} className="flex items-center justify-between gap-3 rounded-lg border border-slate-100 p-3"><div className="min-w-0"><div className="truncate text-sm font-semibold text-slate-800">{row.partner_name}</div><div className="text-xs capitalize text-slate-400">{row.direction} · {row.order_count} orders · {row.currency}</div></div><div className="shrink-0 text-sm font-bold tabular-nums text-slate-800">{money(row.order_value, row.currency)}</div></div>)}</div>}</CardContent></Card>
        <Card><CardHeader className="flex flex-row items-center justify-between gap-2"><div><CardTitle className="text-base">Shipment performance</CardTitle><CardDescription>Arrival dates and calculated days late; live carrier tracking is not implied.</CardDescription></div>{canExportReports && <Button size="sm" variant="outline" onClick={() => void exportCsv('shipment_performance')}><ArrowDownToLine size={14} className="mr-2" />CSV</Button>}</CardHeader><CardContent>{shipmentsQuery.isPending ? <Loading /> : (shipmentsQuery.data ?? []).length === 0 ? <Empty text="No shipments were recorded in this period." /> : <div className="overflow-x-auto"><table className="w-full min-w-[580px] text-left text-sm"><thead className="border-b border-slate-100 text-[11px] uppercase tracking-wide text-slate-400"><tr><th className="py-2">Shipment</th><th>Partner</th><th>Status</th><th>ETA</th><th className="text-right">Days late</th></tr></thead><tbody className="divide-y divide-slate-100">{shipmentsQuery.data?.map((row) => <tr key={`${row.direction}-${row.shipment_id}`}><td className="py-3"><div className="font-semibold text-slate-800">{row.shipment_reference}</div><div className="text-xs capitalize text-slate-400">{row.direction} · {row.order_reference}</div></td><td>{row.partner_name}</td><td className="capitalize">{row.status.replaceAll('_', ' ')}</td><td>{row.estimated_arrival || '—'}</td><td className={`text-right font-semibold ${row.days_late && row.days_late > 0 ? 'text-rose-600' : 'text-slate-600'}`}>{row.days_late ?? '—'}</td></tr>)}</tbody></table></div>}</CardContent></Card>
      </div>

      <Card><CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3"><div><CardTitle className="text-base">Missing required documents</CardTitle><CardDescription>Required documents without a verified upload across active orders and shipments.</CardDescription></div>{canExportReports && <Button size="sm" variant="outline" onClick={() => void exportCsv('missing_documents')}><ArrowDownToLine size={14} className="mr-2" />Export CSV</Button>}</CardHeader><CardContent>{missingDocumentsQuery.isPending ? <Loading /> : missingDocumentsQuery.isError ? <p role="alert" className="text-sm text-rose-600">Could not load missing document report.</p> : (missingDocumentsQuery.data ?? []).length === 0 ? <Empty text="All active required-document checks are satisfied." /> : <div className="overflow-x-auto"><table className="w-full min-w-[650px] text-left text-sm"><thead className="border-b border-slate-100 text-[11px] uppercase tracking-wide text-slate-400"><tr><th className="py-2">Related record</th><th>Partner</th><th>Document</th><th>Document type</th></tr></thead><tbody className="divide-y divide-slate-100">{missingDocumentsQuery.data?.slice(0, 100).map((row) => <tr key={row.requirement_id}><td className="py-3"><div className="font-semibold text-slate-800">{row.record_reference}</div><div className="text-xs capitalize text-slate-400">{row.related_entity_type.replaceAll('_', ' ')}</div></td><td>{row.partner_name}</td><td>{row.label}</td><td className="capitalize">{row.document_type.replaceAll('_', ' ')}</td></tr>)}</tbody></table></div>}</CardContent></Card>

      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400"><FileWarning size={14} />{summaryQuery.data?.missing_required_documents ?? 0} missing or unverified required documents in active trade records. <span className="ml-auto inline-flex items-center gap-1"><Activity size={13} /> Historical period: {startDate} – {endDate}</span></div>
    </div>
  )
}

function Metric({ title, value, icon, detail, warning = false }: { title: string; value: number | string; icon: ReactNode; detail: string; warning?: boolean }) {
  return <Card><CardContent className="flex items-start justify-between p-4"><div><div className="text-xs font-semibold text-slate-500">{title}</div><div className="mt-2 text-2xl font-bold tabular-nums text-slate-900">{value}</div><div className="mt-1 text-[11px] text-slate-400">{detail}</div></div><div className={`rounded-xl p-2 ${warning ? 'bg-amber-50 text-amber-700' : 'bg-sky-50 text-sky-700'}`}>{icon}</div></CardContent></Card>
}
function Balance({ label, value, danger = false }: { label: string; value: string; danger?: boolean }) { return <div><div className="text-[11px] text-slate-400">{label}</div><div className={`mt-1 font-semibold tabular-nums ${danger ? 'text-rose-600' : 'text-slate-800'}`}>{value}</div></div> }
function Loading() { return <div className="animate-pulse space-y-3 py-4"><div className="h-3 w-2/3 rounded bg-slate-100" /><div className="h-3 w-full rounded bg-slate-100" /><div className="h-3 w-5/6 rounded bg-slate-100" /></div> }
function Empty({ text }: { text: string }) { return <div className="rounded-xl border border-dashed border-slate-200 py-8 text-center text-sm text-slate-400">{text}</div> }
