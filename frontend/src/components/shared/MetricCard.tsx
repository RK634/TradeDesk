import type { LucideIcon } from 'lucide-react'
import { ArrowUpRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Card, CardContent } from '@/components/ui/card'

export type MetricTone = 'blue' | 'green' | 'amber' | 'violet'

export interface MetricCardProps {
  label: string
  value: string | number
  detail: string
  icon: LucideIcon
  tone: MetricTone
  trend: string
  href: string
}

const toneClasses: Record<MetricTone, string> = {
  blue: 'bg-blue-50 text-blue-700 ring-blue-100',
  green: 'bg-emerald-50 text-emerald-700 ring-emerald-100',
  amber: 'bg-amber-50 text-amber-700 ring-amber-100',
  violet: 'bg-violet-50 text-violet-700 ring-violet-100',
}

/** Reusable link-backed KPI card; the entire card has a clear working destination. */
export function MetricCard({ label, value, detail, icon: Icon, tone, trend, href }: MetricCardProps) {
  return <Link to={href} className="group block rounded-2xl outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2">
    <Card className="h-full border-slate-200/80 shadow-sm shadow-slate-200/40 transition-all group-hover:-translate-y-0.5 group-hover:border-slate-300 group-hover:shadow-md">
      <CardContent className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="text-sm font-medium text-slate-500">{label}</div>
          <span className={`flex h-10 w-10 items-center justify-center rounded-xl ring-1 ${toneClasses[tone]}`}><Icon size={18} aria-hidden="true" /></span>
        </div>
        <div className="mt-4 flex items-end justify-between gap-3"><div className="text-3xl font-bold tracking-tight text-slate-900">{value}</div><ArrowUpRight className="mb-1 text-slate-300 transition-colors group-hover:text-sky-600" size={18} aria-hidden="true" /></div>
        <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs text-slate-500"><span className="font-semibold text-slate-600">{trend}</span><span>·</span><span>{detail}</span></div>
      </CardContent>
    </Card>
  </Link>
}
