import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'

export function EmptyState({ icon: Icon, title, description, action }: {
  icon: LucideIcon
  title: string
  description: string
  action?: ReactNode
}) {
  return <div className="flex flex-col items-center rounded-2xl border border-dashed border-slate-300 bg-white px-6 py-14 text-center">
    <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-100 text-slate-500"><Icon size={23} aria-hidden="true" /></span>
    <h3 className="mt-4 text-base font-semibold text-slate-900">{title}</h3>
    <p className="mt-2 max-w-md text-sm leading-6 text-slate-500">{description}</p>
    {action && <div className="mt-5">{action}</div>}
  </div>
}
