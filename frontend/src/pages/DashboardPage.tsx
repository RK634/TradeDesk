import { useMemo, useState } from 'react'
import { Link, useOutletContext } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Activity, ArrowDownRight, ArrowRight, ArrowUpRight, Boxes, Building2, CalendarDays,
  CheckCircle2, CircleAlert, Clock3, FileCheck2, PackageCheck, RefreshCw, ShieldCheck,
  Truck, Users, Wallet, Ship, ClipboardCheck,
} from 'lucide-react'
import {
  Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
  Bar, BarChart, Cell,
} from 'recharts'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState } from '@/components/shared/EmptyState'
import { MetricCard } from '@/components/shared/MetricCard'
import { MetricSkeleton } from '@/components/shared/MetricSkeleton'
import type { AppShellOutletContext } from '@/components/layout/AppShell'
import { getDashboardSummary } from '@/features/dashboard/api'
import { useAuth } from '@/features/auth/AuthProvider'

function currencyValue(value: string | number, currency: string) {
  return new Intl.NumberFormat(undefined, { style: 'currency', currency, minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(value || 0))
}

function dateValue(date: Date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function WorkflowGuide() {
  const steps = [
    {
      number: '01',
      title: 'Set up your workspace',
      description: 'Confirm your organization details, invite teammates, and assign the right access roles.',
      result: 'Your team has a shared workspace with clear responsibilities.',
      links: [{ label: 'Organization settings', to: '/app/organization' }],
      icon: Building2,
    },
    {
      number: '02',
      title: 'Add your business records',
      description: 'Create customers, suppliers, products, and warehouse locations before entering trade orders.',
      result: 'Orders can use consistent partner, product, and stock information.',
      links: [{ label: 'Customers', to: '/app/customers' }, { label: 'Suppliers', to: '/app/suppliers' }, { label: 'Products & stock', to: '/app/products' }],
      icon: Boxes,
    },
    {
      number: '03',
      title: 'Create and manage an import',
      description: 'Choose a supplier, add products and quantities, submit the order for approval, and record shipment details.',
      result: 'Confirmed goods receipts increase inventory and create stock movement history.',
      links: [{ label: 'Open import orders', to: '/app/imports' }],
      icon: PackageCheck,
    },
    {
      number: '04',
      title: 'Prepare and deliver an export',
      description: 'Choose a customer, add order lines, obtain approval, reserve available stock, and record dispatches and deliveries.',
      result: 'Approval reserves stock; dispatch deducts on-hand stock; delivery records fulfillment without deducting stock again.',
      links: [{ label: 'Open export orders', to: '/app/exports' }],
      icon: Truck,
    },
    {
      number: '05',
      title: 'Manage shipments and documents',
      description: 'Record shipment milestones, upload trade documents, and send documents for verification.',
      result: 'Your team can review shipment progress and see which documents still need attention.',
      links: [{ label: 'Shipments', to: '/app/shipments' }, { label: 'Documents', to: '/app/documents' }],
      icon: FileCheck2,
    },
    {
      number: '06',
      title: 'Invoice, reconcile, and review',
      description: 'Issue supplier or customer invoices, record partial payments, allocate them, and review reports.',
      result: 'Outstanding balances and financial summaries remain grouped by currency.',
      links: [{ label: 'Invoices & payments', to: '/app/invoices' }, { label: 'Reports', to: '/app/reports' }],
      icon: Wallet,
    },
  ]

  return (
    <Card className="rounded-2xl border-slate-200/80 shadow-sm shadow-slate-200/30">
      <CardHeader className="border-b border-slate-100 px-5 py-5 sm:px-6">
        <div className="flex items-start gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-700"><ClipboardCheck size={19} /></span>
          <div>
            <CardTitle className="text-base">How to use TradeDesk</CardTitle>
            <CardDescription className="mt-1.5 max-w-3xl leading-5">Follow this practical guide to set up your workspace and manage a trade from the first order through delivery and payment.</CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="grid gap-3 p-4 sm:grid-cols-2 sm:p-5 xl:grid-cols-3">
        {steps.map(({ number, title, description, result, links, icon: Icon }) => (
          <article key={number} className="flex flex-col rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex items-center justify-between gap-3">
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-slate-50 text-slate-600"><Icon size={17} /></span>
              <span className="text-xs font-bold tracking-wider text-slate-300">{number}</span>
            </div>
            <h3 className="mt-3 text-sm font-semibold text-slate-900">{title}</h3>
            <p className="mt-1.5 text-xs leading-5 text-slate-600">{description}</p>
            <div className="mt-3 rounded-lg bg-slate-50 px-3 py-2.5">
              <p className="text-[10px] font-bold uppercase tracking-wide text-slate-400">What happens</p>
              <p className="mt-1 text-xs leading-5 text-slate-600">{result}</p>
            </div>
            <div className="mt-auto flex flex-wrap gap-2 pt-3">
              {links.map((link) => <Link key={link.to} to={link.to} className="inline-flex items-center gap-1 text-xs font-semibold text-primary hover:underline">{link.label}<ArrowRight size={12} /></Link>)}
            </div>
          </article>
        ))}
      </CardContent>
    </Card>
  )
}

export function DashboardPage() {
  const { auth } = useAuth()
  const { selectedOrganizationId, selectedOrganization } = useOutletContext<AppShellOutletContext>()
  const [period, setPeriod] = useState('30')
  const today = dateValue(new Date())
  const startDate = useMemo(() => {
    const date = new Date()
    date.setDate(date.getDate() - (Number(period) - 1))
    return dateValue(date)
  }, [period])
  const summaryQuery = useQuery({
    queryKey: ['dashboard', 'summary', selectedOrganizationId, startDate, today],
    queryFn: () => getDashboardSummary({ organizationId: selectedOrganizationId, startDate, endDate: today }),
    enabled: Boolean(selectedOrganizationId),
    retry: false,
  })
  const summary = summaryQuery.data
  const firstName = auth?.user.full_name.trim().split(/\s+/)[0] || 'there'
  const formattedPeriod = `${new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(new Date(`${startDate}T12:00:00`))} – ${new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' }).format(new Date(`${today}T12:00:00`))}`

  return <div className="space-y-7">
    <section className="relative overflow-hidden rounded-2xl bg-[#122338] px-5 py-6 text-white shadow-lg shadow-slate-900/10 sm:px-7 sm:py-7">
      <div aria-hidden="true" className="pointer-events-none absolute -right-10 -top-24 h-64 w-64 rounded-full border border-white/10" />
      <div aria-hidden="true" className="pointer-events-none absolute -right-2 -top-16 h-48 w-48 rounded-full border border-white/10" />
      <div className="relative flex flex-col justify-between gap-5 md:flex-row md:items-end">
        <div><div className="mb-3 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/[0.07] px-3 py-1.5 text-[11px] font-semibold text-sky-200"><span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />WORKSPACE OVERVIEW</div><h2 className="text-2xl font-bold tracking-tight sm:text-3xl">Good to see you, {firstName}.</h2><p className="mt-2 max-w-xl text-sm leading-6 text-slate-300">Review your workspace, active import orders, approvals, and goods receipts from one place.</p></div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex h-10 items-center gap-2 rounded-lg border border-white/15 bg-white/[0.08] px-3 text-xs font-semibold text-white"><CalendarDays size={15} className="text-sky-200" /><select value={period} onChange={(event) => setPeriod(event.target.value)} aria-label="Dashboard date range" className="bg-transparent outline-none"><option className="text-slate-900" value="7">Last 7 days</option><option className="text-slate-900" value="30">Last 30 days</option><option className="text-slate-900" value="90">Last 90 days</option><option className="text-slate-900" value="365">Last 12 months</option></select></label>
          <Button variant="outline" className="border-white/20 bg-white/[0.08] text-white hover:bg-white/[0.14] hover:text-white" onClick={() => summaryQuery.refetch()} disabled={summaryQuery.isFetching}><RefreshCw size={14} className={summaryQuery.isFetching ? 'animate-spin' : ''} />Refresh</Button>
        </div>
      </div>
      <div className="relative mt-5 flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-white/10 pt-4 text-xs text-slate-300"><span className="inline-flex items-center gap-2"><Building2 size={14} className="text-sky-200" />{selectedOrganization?.organization_name ?? 'Select an organization'}</span><span className="hidden h-3 w-px bg-white/20 sm:block" /><span className="inline-flex items-center gap-2"><CalendarDays size={14} className="text-sky-200" />{formattedPeriod}</span>{summary && <><span className="hidden h-3 w-px bg-white/20 sm:block" /><span className="inline-flex items-center gap-2"><CheckCircle2 size={14} className="text-emerald-300" />Updated {new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit' }).format(new Date(summary.generated_at))}</span></>}</div>
    </section>

    {!selectedOrganizationId ? <EmptyState icon={Building2} title="Create your first organization" description="A dashboard is scoped to an organization. Create one to begin managing your workspace and team." action={<Link to="/app/organization" className="inline-flex h-10 items-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground shadow-sm hover:bg-primary/90">Open organization settings <ArrowRight size={15} /></Link>} /> : null}

    {selectedOrganizationId ? <WorkflowGuide /> : null}

    {selectedOrganizationId && summaryQuery.isPending ? <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Loading dashboard metrics" role="status"><MetricSkeleton /><MetricSkeleton /><MetricSkeleton /><MetricSkeleton /></div> : null}

    {selectedOrganizationId && summaryQuery.isError ? <Card className="rounded-2xl border-rose-200 bg-rose-50/70"><CardContent className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between"><div className="flex gap-3"><span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-rose-100 text-rose-700"><CircleAlert size={19} /></span><div><h3 className="font-semibold text-rose-900">Dashboard data could not be loaded</h3><p className="mt-1 text-sm text-rose-800">{summaryQuery.error instanceof Error ? summaryQuery.error.message : 'Check your connection and organization access, then try again.'}</p></div></div><Button variant="outline" onClick={() => summaryQuery.refetch()} disabled={summaryQuery.isFetching}><RefreshCw size={14} />Retry</Button></CardContent></Card> : null}

    {summary && <>
      <section aria-label="Workspace metrics" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Active members" value={summary.workspace.active_members} detail="with active access" icon={Users} tone="blue" trend="Current" href="/app/organization" />
        <MetricCard label="New members" value={summary.workspace.new_members} detail={`between ${summary.period_start} and ${summary.period_end}`} icon={ArrowUpRight} tone="green" trend="In selected period" href="/app/organization" />
        <MetricCard label="Inactive members" value={summary.workspace.inactive_members} detail="membership access disabled" icon={ArrowDownRight} tone="amber" trend="Current" href="/app/organization" />
        {summary.workspace.can_view_invitations ? <MetricCard label="Pending invitations" value={summary.workspace.pending_invitations ?? 0} detail="awaiting acceptance" icon={Clock3} tone="violet" trend="Not expired" href="/app/organization" /> : <MetricCard label="Pending invitations" value="—" detail="restricted for your role" icon={ShieldCheck} tone="violet" trend="Access controlled" href="/app/organization" />}
      </section>

      {summary.import_metrics && <section aria-label="Import operation metrics" className="space-y-3">
        <div><h3 className="text-sm font-semibold text-slate-800">Import operations</h3><p className="mt-1 text-xs text-slate-500">Live counts for this organization, calculated from import orders and shipments.</p></div>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard label="Active import orders" value={summary.import_metrics.active_orders} detail="submitted, approved, or partially received" icon={PackageCheck} tone="blue" trend="Current" href="/app/imports" />
          <MetricCard label="Awaiting approval" value={summary.import_metrics.awaiting_approval} detail="submitted orders" icon={ClipboardCheck} tone="violet" trend="Action needed" href="/app/imports" />
          <MetricCard label="Partially received" value={summary.import_metrics.partially_received} detail="more goods are still expected" icon={Boxes} tone="amber" trend="Receiving" href="/app/imports" />
          <MetricCard label="Goods received" value={summary.import_metrics.received} detail="fully received import orders" icon={CheckCircle2} tone="green" trend="Completed receipts" href="/app/imports" />
          <MetricCard label="Delayed shipments" value={summary.import_metrics.delayed_shipments} detail="manually marked delayed" icon={Ship} tone="amber" trend="Review" href="/app/imports" />
        </div>
      </section>}

      {summary.export_metrics && <section aria-label="Export operation metrics" className="space-y-3">
        <div><h3 className="text-sm font-semibold text-slate-800">Export operations</h3><p className="mt-1 text-xs text-slate-500">Live counts from export orders, stock-backed dispatches, and delivery records.</p></div>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <MetricCard label="Active export orders" value={summary.export_metrics.active_orders} detail="submitted, approved, or in fulfillment" icon={Truck} tone="blue" trend="Current" href="/app/exports" />
          <MetricCard label="Awaiting export approval" value={summary.export_metrics.awaiting_approval} detail="submitted orders" icon={ClipboardCheck} tone="violet" trend="Action needed" href="/app/exports" />
          <MetricCard label="Partially delivered" value={summary.export_metrics.partially_delivered} detail="deliveries remain outstanding" icon={Boxes} tone="amber" trend="In progress" href="/app/exports" />
          <MetricCard label="Delivered exports" value={summary.export_metrics.delivered} detail="fully delivered export orders" icon={CheckCircle2} tone="green" trend="Completed" href="/app/exports" />
          <MetricCard label="Delayed export shipments" value={summary.export_metrics.delayed_shipments} detail="manually marked delayed" icon={Ship} tone="amber" trend="Review" href="/app/exports" />
        </div>
      </section>}

      {summary.financial_metrics && <section aria-label="Financial exposure by currency" className="space-y-3">
        <div><h3 className="text-sm font-semibold text-slate-800">Outstanding financial exposure</h3><p className="mt-1 text-xs text-slate-500">Customer receivables and supplier payables are grouped by currency. Different currencies are never added together.</p></div>
        {summary.financial_metrics.length > 0 ? <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm"><table className="w-full min-w-[700px] text-left text-sm"><thead className="bg-slate-50 text-[11px] uppercase tracking-wide text-slate-500"><tr><th className="px-4 py-3">Currency</th><th className="px-4 py-3 text-right">Customer receivables</th><th className="px-4 py-3 text-right">Supplier payables</th><th className="px-4 py-3 text-right">Overdue receivables</th><th className="px-4 py-3 text-right">Overdue payables</th><th className="px-4 py-3 text-right">Open invoices</th></tr></thead><tbody>{summary.financial_metrics.map((row) => <tr key={row.currency} className="border-t border-slate-100"><td className="px-4 py-3 font-semibold text-slate-800">{row.currency}</td><td className="px-4 py-3 text-right font-medium">{currencyValue(row.customer_receivables, row.currency)}</td><td className="px-4 py-3 text-right font-medium">{currencyValue(row.supplier_payables, row.currency)}</td><td className="px-4 py-3 text-right text-rose-700">{currencyValue(row.overdue_customer, row.currency)}</td><td className="px-4 py-3 text-right text-rose-700">{currencyValue(row.overdue_supplier, row.currency)}</td><td className="px-4 py-3 text-right">{row.open_invoice_count}</td></tr>)}</tbody></table></div> : <div className="rounded-xl border border-dashed border-slate-300 bg-white px-5 py-8 text-center"><Wallet size={24} className="mx-auto text-slate-300" /><p className="mt-2 text-sm font-semibold text-slate-700">No outstanding invoices</p><p className="mt-1 text-xs text-slate-500">Issued invoices with unpaid balances will appear here.</p></div>}
      </section>}

      <section className="grid gap-5 xl:grid-cols-[1.55fr_1fr]">
        <Card className="rounded-2xl border-slate-200/80 shadow-sm shadow-slate-200/30">
          <CardHeader className="flex flex-row items-start justify-between space-y-0 border-b border-slate-100 px-5 py-5 sm:px-6"><div><CardTitle className="text-base">Team growth</CardTitle><CardDescription className="mt-1.5">Memberships created during {summary.period_start} to {summary.period_end}.</CardDescription></div><span className="rounded-xl bg-sky-50 p-2.5 text-sky-700"><Activity size={18} /></span></CardHeader>
          <CardContent className="pt-5"><div className="h-[255px] w-full" role="img" aria-label="Line chart showing new organization memberships by day"><ResponsiveContainer width="100%" height="100%"><AreaChart data={summary.member_join_trend} margin={{ top: 8, right: 8, left: -22, bottom: 0 }}><defs><linearGradient id="teamGrowthFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#0f75bd" stopOpacity={0.23} /><stop offset="95%" stopColor="#0f75bd" stopOpacity={0.015} /></linearGradient></defs><CartesianGrid stroke="#e8edf3" strokeDasharray="4 4" vertical={false} /><XAxis dataKey="label" axisLine={false} tickLine={false} tick={{ fill: '#8793a3', fontSize: 10 }} interval={Math.max(0, Math.ceil(summary.member_join_trend.length / 7) - 1)} /><YAxis allowDecimals={false} axisLine={false} tickLine={false} tick={{ fill: '#8793a3', fontSize: 11 }} /><Tooltip contentStyle={{ borderRadius: 12, borderColor: '#e2e8f0', fontSize: 12 }} formatter={(value) => [value, 'New members']} /><Area type="monotone" dataKey="count" stroke="#0f75bd" strokeWidth={2.5} fill="url(#teamGrowthFill)" activeDot={{ r: 4, strokeWidth: 0 }} /></AreaChart></ResponsiveContainer></div></CardContent>
        </Card>

        <Card className="rounded-2xl border-slate-200/80 shadow-sm shadow-slate-200/30">
          <CardHeader className="flex flex-row items-start justify-between space-y-0 border-b border-slate-100 px-5 py-5 sm:px-6"><div><CardTitle className="text-base">Active members by role</CardTitle><CardDescription className="mt-1.5">Current access distribution in this organization.</CardDescription></div><span className="rounded-xl bg-violet-50 p-2.5 text-violet-700"><Users size={18} /></span></CardHeader>
          <CardContent className="pt-5"><div className="h-[255px] w-full" role="img" aria-label="Bar chart showing active member counts by role">{summary.members_by_role.length > 0 ? <ResponsiveContainer width="100%" height="100%"><BarChart data={summary.members_by_role} layout="vertical" margin={{ top: 3, right: 12, left: 8, bottom: 0 }}><CartesianGrid stroke="#e8edf3" strokeDasharray="4 4" horizontal={false} /><XAxis type="number" allowDecimals={false} axisLine={false} tickLine={false} tick={{ fill: '#8793a3', fontSize: 10 }} /><YAxis type="category" dataKey="label" width={115} axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 10 }} /><Tooltip cursor={{ fill: '#f1f5f9' }} contentStyle={{ borderRadius: 12, borderColor: '#e2e8f0', fontSize: 12 }} formatter={(value) => [value, 'Members']} /><Bar dataKey="count" radius={[0, 5, 5, 0]} barSize={19}>{summary.members_by_role.map((item, index) => <Cell key={item.role} fill={['#1677b8', '#20a486', '#7266ca', '#d79535', '#65758b', '#ad6b90', '#6a9c78'][index % 7]} />)}</Bar></BarChart></ResponsiveContainer> : <div className="flex h-full flex-col items-center justify-center text-center"><Users size={26} className="text-slate-300" /><p className="mt-3 text-sm font-medium text-slate-600">No active members</p><p className="mt-1 text-xs text-slate-400">Role counts appear when members are added.</p></div>}</div></CardContent>
        </Card>
      </section>



      <section className="flex flex-col justify-between gap-4 rounded-2xl border border-slate-200 bg-white px-5 py-4 sm:flex-row sm:items-center sm:px-6">
        <div className="flex gap-3"><span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-600"><Building2 size={18} /></span><div><h3 className="text-sm font-semibold">Need to manage your team?</h3><p className="mt-1 text-xs leading-5 text-slate-500">Invite teammates and review access roles in organization settings.</p></div></div>
        <Link to="/app/organization" className="inline-flex h-10 items-center gap-2 rounded-md border bg-white px-4 text-sm font-medium shadow-sm hover:bg-slate-50">Manage organization <ArrowRight size={15} /></Link>
      </section>
    </>}

    <footer className="flex flex-wrap items-center justify-between gap-2 pb-2 text-[11px] text-slate-400"><span>TradeDesk · Importer & Exporter Management</span><span>Dashboard data is scoped to the active organization.</span></footer>
  </div>
}
