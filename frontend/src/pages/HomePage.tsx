import { Link, Navigate } from 'react-router-dom'
import {
  ArrowRight, ArrowUpRight, Boxes, CheckCircle2, ClipboardCheck, FileCheck2,
  Globe2, PackageCheck, ShieldCheck, Ship, Users, Wallet,
} from 'lucide-react'
import { useAuth } from '@/features/auth/AuthProvider'

const features = [
  {
    icon: PackageCheck,
    title: 'Import and export orders',
    description: 'Create trade orders, manage approvals, record shipments, and follow each order through receipt or delivery.',
  },
  {
    icon: Boxes,
    title: 'Products and inventory',
    description: 'Maintain product records, warehouse locations, stock balances, reservations, and a traceable movement ledger.',
  },
  {
    icon: Ship,
    title: 'Shipments and documents',
    description: 'Track shipment milestones, record delays, upload private trade documents, and manage verification history.',
  },
  {
    icon: Wallet,
    title: 'Invoices and payments',
    description: 'Create customer and supplier invoices, allocate partial payments, and review outstanding balances by currency.',
  },
  {
    icon: ClipboardCheck,
    title: 'Tasks and approvals',
    description: 'Assign work, set due dates, route supported actions for approval, and keep a history of decisions.',
  },
  {
    icon: FileCheck2,
    title: 'Reports and archive',
    description: 'Review operational and financial reports, export permitted data, and preserve completed orders for later reference.',
  },
]

const workflow = [
  { number: '01', title: 'Set up your workspace', detail: 'Add your organization details, invite your team, and assign access roles.' },
  { number: '02', title: 'Add your business records', detail: 'Create customers, suppliers, products, and the warehouse locations where stock is held.' },
  { number: '03', title: 'Manage a trade order', detail: 'Create an import or export order, submit it for approval, and record shipment information.' },
  { number: '04', title: 'Complete the transaction', detail: 'Receive imported goods or deliver exported goods, verify documents, issue invoices, and record payments.' },
  { number: '05', title: 'Review and retain records', detail: 'Monitor tasks and reminders, review reports, and archive eligible completed orders.' },
]

export function HomePage() {
  const { auth, isLoading } = useAuth()

  if (isLoading) {
    return <main className="flex min-h-screen items-center justify-center bg-slate-50 text-sm text-slate-500">Loading TradeDesk…</main>
  }

  // Authenticated users should land directly in their workspace, not see the public product page.
  if (auth) return <Navigate to="/app" replace />

  return (
    <main className="min-h-screen bg-white text-slate-900">
      <header className="sticky top-0 z-30 border-b border-slate-200/80 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-4 sm:px-8">
          <a href="/" className="flex items-center gap-3 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600" aria-label="TradeDesk home">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#174785] text-white"><Globe2 size={21} aria-hidden="true" /></span>
            <span>
              <span className="block text-base font-bold tracking-tight">TradeDesk</span>
              <span className="block text-xs text-slate-500">Importer & Exporter Management</span>
            </span>
          </a>
          <nav className="hidden items-center gap-7 md:flex" aria-label="Public navigation">
            <a href="#features" className="text-sm font-medium text-slate-600 hover:text-[#174785]">Features</a>
            <a href="#how-it-works" className="text-sm font-medium text-slate-600 hover:text-[#174785]">How it works</a>
            <a href="#control" className="text-sm font-medium text-slate-600 hover:text-[#174785]">Control & security</a>
          </nav>
          <div className="flex items-center gap-2">
            <Link to="/login" className="rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50">Sign in</Link>
            <Link to="/register" className="inline-flex items-center gap-2 rounded-lg bg-[#174785] px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-[#123968]">
              Create workspace <ArrowUpRight size={15} aria-hidden="true" />
            </Link>
          </div>
        </div>
      </header>

      <section className="overflow-hidden bg-gradient-to-b from-[#f3f7fc] to-white">
        <div className="mx-auto grid max-w-7xl items-center gap-12 px-5 py-16 sm:px-8 sm:py-24 lg:grid-cols-[1.05fr_0.95fr]">
          <div>
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-blue-100 bg-white px-3.5 py-2 text-xs font-semibold text-[#174785] shadow-sm">
              <Globe2 size={14} aria-hidden="true" /> One workspace for international trade
            </div>
            <h1 className="max-w-3xl text-4xl font-bold leading-[1.08] tracking-tight text-slate-950 sm:text-5xl lg:text-6xl">
              Manage every trade, <span className="text-[#174785]">from order to settlement.</span>
            </h1>
            <p className="mt-6 max-w-2xl text-base leading-8 text-slate-600 sm:text-lg">
              TradeDesk brings import and export orders, inventory, shipments, documents, invoices, payments, and team work into one organized business workspace.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to="/register" className="inline-flex h-12 items-center gap-2 rounded-lg bg-[#174785] px-5 text-sm font-semibold text-white shadow-sm transition hover:bg-[#123968]">
                Get started <ArrowRight size={16} aria-hidden="true" />
              </Link>
              <a href="#how-it-works" className="inline-flex h-12 items-center rounded-lg border border-slate-300 bg-white px-5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50">See how it works</a>
            </div>
            <div className="mt-8 flex flex-wrap gap-x-6 gap-y-3 text-xs font-medium text-slate-500">
              <span className="inline-flex items-center gap-2"><CheckCircle2 size={15} className="text-emerald-600" /> Organization-based workspaces</span>
              <span className="inline-flex items-center gap-2"><CheckCircle2 size={15} className="text-emerald-600" /> Role-based access</span>
              <span className="inline-flex items-center gap-2"><CheckCircle2 size={15} className="text-emerald-600" /> Traceable business records</span>
            </div>
          </div>

          <div className="relative mx-auto w-full max-w-xl">
            <div className="absolute -left-8 top-12 h-40 w-40 rounded-full bg-blue-100/80 blur-3xl" aria-hidden="true" />
            <div className="absolute -bottom-8 right-0 h-44 w-44 rounded-full bg-emerald-100/70 blur-3xl" aria-hidden="true" />
            <div className="relative rounded-2xl border border-slate-200 bg-white p-5 shadow-2xl shadow-slate-200/70 sm:p-7">
              <div className="flex items-start justify-between gap-4 border-b border-slate-100 pb-5">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">Trade lifecycle</p>
                  <h2 className="mt-2 text-xl font-bold text-slate-900">One connected process</h2>
                  <p className="mt-1 text-sm text-slate-500">Keep each team and record in context.</p>
                </div>
                <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-blue-50 text-[#174785]"><Globe2 size={22} /></span>
              </div>
              <div className="space-y-3 py-5">
                {[
                  { icon: PackageCheck, title: 'Orders & approvals', detail: 'Create import and export orders' },
                  { icon: Boxes, title: 'Inventory & fulfillment', detail: 'Receive, reserve, and dispatch stock' },
                  { icon: Ship, title: 'Shipments & documents', detail: 'Record milestones and verify files' },
                  { icon: Wallet, title: 'Invoices & payments', detail: 'Track amounts due and payments made' },
                ].map(({ icon: Icon, title, detail }, index) => (
                  <div key={title} className="flex items-center gap-3 rounded-xl border border-slate-100 bg-slate-50/80 p-3.5">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-white text-[#174785] shadow-sm"><Icon size={18} /></span>
                    <div className="min-w-0 flex-1"><p className="text-sm font-semibold text-slate-800">{title}</p><p className="mt-0.5 text-xs text-slate-500">{detail}</p></div>
                    <span className="text-xs font-semibold text-slate-300">0{index + 1}</span>
                  </div>
                ))}
              </div>
              <div className="rounded-xl bg-[#122338] px-4 py-3.5 text-white">
                <div className="flex items-center gap-2 text-sm font-semibold"><ShieldCheck size={16} className="text-emerald-300" /> Clear ownership and history</div>
                <p className="mt-1 text-xs leading-5 text-slate-300">Keep activities connected to the organization, order, shipment, or financial record they belong to.</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="features" className="scroll-mt-24 py-16 sm:py-20">
        <div className="mx-auto max-w-7xl px-5 sm:px-8">
          <div className="max-w-2xl">
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-[#174785]">What you can manage</p>
            <h2 className="mt-3 text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl">The moving parts of trade, connected.</h2>
            <p className="mt-4 text-base leading-7 text-slate-600">Keep operational, logistics, and financial information together instead of searching across disconnected spreadsheets and messages.</p>
          </div>
          <div className="mt-9 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {features.map(({ icon: Icon, title, description }) => (
              <article key={title} className="rounded-2xl border border-slate-200 bg-white p-6 transition hover:-translate-y-0.5 hover:shadow-lg hover:shadow-slate-200/50">
                <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-blue-50 text-[#174785]"><Icon size={21} aria-hidden="true" /></span>
                <h3 className="mt-5 text-base font-bold text-slate-900">{title}</h3>
                <p className="mt-2 text-sm leading-6 text-slate-600">{description}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section id="how-it-works" className="scroll-mt-24 bg-slate-50 py-16 sm:py-20">
        <div className="mx-auto grid max-w-7xl gap-10 px-5 sm:px-8 lg:grid-cols-[0.8fr_1.2fr]">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-[#174785]">A straightforward start</p>
            <h2 className="mt-3 text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl">How TradeDesk works</h2>
            <p className="mt-4 max-w-md text-sm leading-7 text-slate-600">Start with your organization and business records. Then follow each trade from its first order through shipment, delivery, and payment reconciliation.</p>
            <Link to="/register" className="mt-7 inline-flex h-11 items-center gap-2 rounded-lg bg-[#174785] px-5 text-sm font-semibold text-white hover:bg-[#123968]">Set up your workspace <ArrowRight size={15} /></Link>
          </div>
          <div className="space-y-3">
            {workflow.map((item) => (
              <div key={item.number} className="flex gap-4 rounded-xl border border-slate-200 bg-white p-5">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-sm font-bold text-[#174785]">{item.number}</span>
                <div><h3 className="text-sm font-bold text-slate-900">{item.title}</h3><p className="mt-1.5 text-sm leading-6 text-slate-600">{item.detail}</p></div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="control" className="scroll-mt-24 py-16 sm:py-20">
        <div className="mx-auto max-w-7xl px-5 sm:px-8">
          <div className="rounded-3xl bg-[#122338] px-6 py-10 text-white sm:px-10 sm:py-12">
            <div className="grid gap-9 lg:grid-cols-[1fr_1fr] lg:items-center">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.18em] text-sky-300">Built for business control</p>
                <h2 className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">Know what happened, who did it, and what comes next.</h2>
                <p className="mt-4 max-w-xl text-sm leading-7 text-slate-300">TradeDesk is designed around organization-scoped access, traceable inventory movements, financial records, and controlled document access.</p>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                {[
                  { icon: Users, title: 'Team permissions', detail: 'Give employees access appropriate to their responsibilities.' },
                  { icon: ShieldCheck, title: 'Organization boundaries', detail: 'Keep each organization’s business records scoped to its members.' },
                  { icon: Boxes, title: 'Traceable stock', detail: 'Record receipts, reservations, dispatches, and adjustments.' },
                  { icon: FileCheck2, title: 'Private documents', detail: 'Manage business files through authorized application access.' },
                ].map(({ icon: Icon, title, detail }) => <div key={title} className="rounded-xl border border-white/10 bg-white/[0.06] p-4"><Icon size={19} className="text-sky-300" /><h3 className="mt-3 text-sm font-semibold">{title}</h3><p className="mt-1.5 text-xs leading-5 text-slate-300">{detail}</p></div>)}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="border-t border-slate-200 bg-white py-14">
        <div className="mx-auto flex max-w-7xl flex-col items-start justify-between gap-5 px-5 sm:flex-row sm:items-center sm:px-8">
          <div><h2 className="text-2xl font-bold tracking-tight text-slate-950">Bring your trade operations into one workspace.</h2><p className="mt-2 text-sm text-slate-600">Create your organization and invite your team to get started.</p></div>
          <Link to="/register" className="inline-flex h-11 shrink-0 items-center gap-2 rounded-lg bg-[#174785] px-5 text-sm font-semibold text-white hover:bg-[#123968]">Create your workspace <ArrowRight size={15} /></Link>
        </div>
      </section>

      <footer className="border-t border-slate-200 bg-slate-50">
        <div className="mx-auto flex max-w-7xl flex-col gap-3 px-5 py-7 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between sm:px-8">
          <span className="font-semibold text-slate-700">TradeDesk · Importer & Exporter Management</span>
          <div className="flex gap-4"><Link to="/login" className="hover:text-[#174785]">Sign in</Link><Link to="/register" className="hover:text-[#174785]">Create workspace</Link></div>
          <span>Manage orders, stock, shipments, documents, and finance.</span>
        </div>
      </footer>
    </main>
  )
}
