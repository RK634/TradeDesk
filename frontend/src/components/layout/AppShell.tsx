import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  Archive, BarChart3, Bell, Boxes, Building2, CheckSquare, ChevronDown, CircleDollarSign,
  ClipboardList, FileCheck2, Globe2, LayoutDashboard, Menu, PackageCheck,
  Search, Settings2, Ship, Truck, Users, Wallet, X, LogOut, Warehouse,
} from 'lucide-react'
import { useAuth } from '@/features/auth/AuthProvider'
import { Button } from '@/components/ui/button'
import type { OrganizationMembership } from '@/features/auth/types'
import { getUnreadCount } from '@/features/workflow/api'

interface NavigationItem {
  label: string
  path: string
  icon: typeof LayoutDashboard
  exact?: boolean
}
interface NavigationGroup { title: string; items: NavigationItem[] }

const navigation: NavigationGroup[] = [
  { title: 'Workspace', items: [{ label: 'Dashboard', path: '/app', icon: LayoutDashboard, exact: true }] },
  { title: 'Trade operations', items: [
    { label: 'Import orders', path: '/app/imports', icon: PackageCheck },
    { label: 'Export orders', path: '/app/exports', icon: Truck },
  ] },
  { title: 'Partners & stock', items: [
    { label: 'Customers', path: '/app/customers', icon: Users },
    { label: 'Suppliers', path: '/app/suppliers', icon: Building2 },
    { label: 'Products', path: '/app/products', icon: Boxes },
    { label: 'Inventory', path: '/app/inventory', icon: ClipboardList },
    { label: 'Locations', path: '/app/locations', icon: Warehouse },
  ] },
  { title: 'Logistics', items: [
    { label: 'Shipments', path: '/app/shipments', icon: Ship },
    { label: 'Documents', path: '/app/documents', icon: FileCheck2 },
  ] },
  { title: 'Work management', items: [
    { label: 'Tasks', path: '/app/tasks', icon: ClipboardList },
    { label: 'Approvals', path: '/app/approvals', icon: CheckSquare },
    { label: 'Notifications', path: '/app/notifications', icon: Bell },
  ] },
  { title: 'Finance & insights', items: [
    { label: 'Invoices', path: '/app/invoices', icon: CircleDollarSign },
    { label: 'Payments', path: '/app/payments', icon: Wallet },
    { label: 'Reports', path: '/app/reports', icon: BarChart3 },
    { label: 'Archive', path: '/app/archive', icon: Archive },
  ] },
  { title: 'Administration', items: [{ label: 'Organization & members', path: '/app/organization', icon: Settings2 }] },
]

export interface AppShellOutletContext {
  selectedOrganizationId: string
  setSelectedOrganizationId: (id: string) => void
  selectedOrganization: OrganizationMembership | undefined
}


export function AppShell() {
  const { auth, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [mobileNavigationOpen, setMobileNavigationOpen] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedOrganizationId, setSelectedOrganizationIdState] = useState('')
  const organizations = auth?.organizations ?? []

  useEffect(() => {
    const saved = window.localStorage.getItem('iem-selected-organization')
    const savedOrganization = saved ? organizations.find((org) => org.organization_id === saved) : undefined
    const currentIsAllowed = organizations.some((org) => org.organization_id === selectedOrganizationId)
    // When a new organization has just been created, preserve that pending selection
    // while the auth/organization queries refresh and confirm its membership.
    const selectionIsPendingRefresh = Boolean(selectedOrganizationId && saved === selectedOrganizationId)
    if (organizations.length > 0 && !currentIsAllowed && !selectionIsPendingRefresh) {
      setSelectedOrganizationIdState(savedOrganization?.organization_id ?? organizations[0].organization_id)
    }
    if (organizations.length > 0 && !selectedOrganizationId) {
      setSelectedOrganizationIdState(savedOrganization?.organization_id ?? organizations[0].organization_id)
    }
  }, [organizations, selectedOrganizationId])

  function setSelectedOrganizationId(id: string) {
    // This is a UI preference only. Every API endpoint still authorizes the organization on the server.
    setSelectedOrganizationIdState(id)
    window.localStorage.setItem('iem-selected-organization', id)
  }

  const selectedOrganization = organizations.find((org) => org.organization_id === selectedOrganizationId)
  const unreadQuery = useQuery({ queryKey: ['workflow', 'unread-count', selectedOrganizationId], queryFn: () => getUnreadCount(selectedOrganizationId), enabled: Boolean(selectedOrganizationId), staleTime: 30_000, retry: false })
  const unreadCount = unreadQuery.data?.unread_count ?? 0
  const canReadFinance = ['organization_owner', 'administrator', 'finance_staff', 'read_only'].includes(selectedOrganization?.role ?? '')
  const canReadReports = ['organization_owner', 'administrator', 'finance_staff', 'read_only'].includes(selectedOrganization?.role ?? '')
  const canReadArchive = ['organization_owner', 'administrator', 'read_only'].includes(selectedOrganization?.role ?? '')
  const normalizedSearch = searchTerm.trim().toLowerCase()
  const filteredNavigation = useMemo(() => navigation.map((group) => ({
    ...group,
    items: group.items.filter((item) => {
      const financeItem = item.path === '/app/invoices' || item.path === '/app/payments'
      const reportItem = item.path === '/app/reports'
      const archiveItem = item.path === '/app/archive'
      const matchesSearch = item.label.toLowerCase().includes(normalizedSearch) || group.title.toLowerCase().includes(normalizedSearch)
      return (!financeItem || canReadFinance) && (!reportItem || canReadReports) && (!archiveItem || canReadArchive) && matchesSearch
    }),
  })).filter((group) => group.items.length > 0), [normalizedSearch, canReadFinance, canReadReports, canReadArchive])

  const pageTitles: Record<string, string> = {
    '/app': 'Dashboard',
    '/app/organization': 'Organization & members',
    '/app/customers': 'Customers',
    '/app/suppliers': 'Suppliers',
    '/app/products': 'Products',
    '/app/inventory': 'Inventory',
    '/app/locations': 'Inventory locations',
    '/app/imports': 'Import management',
    '/app/exports': 'Export management',
    '/app/shipments': 'Shipment tracking',
    '/app/documents': 'Trade documents',
    '/app/invoices': 'Invoices',
    '/app/payments': 'Payments',
    '/app/tasks': 'Tasks',
    '/app/approvals': 'Approvals',
    '/app/notifications': 'Notifications',
    '/app/reports': 'Reports & analytics',
    '/app/archive': 'Archive',
  }
  const pageTitle = pageTitles[location.pathname] ?? 'Trade workspace'

  async function onLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      {mobileNavigationOpen && <button aria-label="Close navigation overlay" className="fixed inset-0 z-30 bg-slate-950/40 lg:hidden" onClick={() => setMobileNavigationOpen(false)} />}
      <aside className={`fixed inset-y-0 left-0 z-40 flex w-[258px] flex-col border-r border-slate-800 bg-[#122338] text-slate-200 transition-transform duration-200 lg:translate-x-0 ${mobileNavigationOpen ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="flex h-[72px] items-center justify-between border-b border-white/10 px-5">
          <Link to="/app" className="flex items-center gap-3 rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-sky-400" onClick={() => setMobileNavigationOpen(false)}>
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-400 text-slate-950"><Globe2 size={21} /></span>
            <span><span className="block text-sm font-bold tracking-wide text-white">TradeDesk</span><span className="mt-0.5 block text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-400">Global trade workspace</span></span>
          </Link>
          <button className="rounded-md p-2 text-slate-400 hover:bg-white/10 lg:hidden" aria-label="Close navigation" onClick={() => setMobileNavigationOpen(false)}><X size={18} /></button>
        </div>

        <div className="px-4 pb-2 pt-5">
          <div className="mb-2 px-2 text-[10px] font-bold uppercase tracking-[0.17em] text-slate-500">Navigation</div>
          <label className="flex h-9 items-center gap-2 rounded-lg border border-white/10 bg-white/[0.06] px-2.5 text-slate-400 focus-within:border-sky-400/60 focus-within:ring-1 focus-within:ring-sky-400/40">
            <Search size={14} aria-hidden="true" />
            <input value={searchTerm} onChange={(event) => setSearchTerm(event.target.value)} className="min-w-0 flex-1 bg-transparent text-xs text-white outline-none placeholder:text-slate-500" placeholder="Search navigation…" aria-label="Search navigation" />
            {searchTerm && <button type="button" className="text-slate-400 hover:text-white" aria-label="Clear navigation search" onClick={() => setSearchTerm('')}><X size={13} /></button>}
          </label>
        </div>

        <nav className="flex-1 space-y-5 overflow-y-auto px-3 pb-5 pt-2" aria-label="Main navigation">
          {filteredNavigation.map((group) => <div key={group.title}>
            <h2 className="mb-2 px-3 text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">{group.title}</h2>
            <div className="space-y-1">
              {group.items.map((item) => {
                const Icon = item.icon
                return <NavLink key={item.label} to={item.path} end={item.exact} onClick={() => setMobileNavigationOpen(false)} className={({ isActive }) => `group flex min-h-10 items-center gap-3 rounded-lg px-3 py-2 text-[13px] font-medium transition-colors ${isActive ? 'bg-sky-400 text-slate-950 shadow-sm' : 'text-slate-300 hover:bg-white/[0.07] hover:text-white'}`}>
                  <Icon size={17} className="shrink-0" aria-hidden="true" /><span className="min-w-0 flex-1">{item.label}</span>
                </NavLink>
              })}
            </div>
          </div>)}
          {filteredNavigation.length === 0 && <p className="px-3 py-5 text-xs leading-5 text-slate-400">No navigation items match “{searchTerm}”.</p>}
        </nav>

        <div className="border-t border-white/10 p-4">
          <div className="rounded-xl border border-white/10 bg-white/[0.04] p-3">
            <div className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-emerald-400" /><span className="text-[11px] font-semibold text-slate-200">Master data & workspace</span></div>
            <p className="mt-2 text-[11px] leading-4 text-slate-400">Manage partners, products, stock, trade orders, shipments, documents, invoices, tasks, and reports from one workspace.</p>
          </div>
        </div>
      </aside>

      <div className="min-h-screen lg:pl-[258px]">
        <header className="sticky top-0 z-20 border-b border-slate-200/80 bg-white/90 backdrop-blur-xl">
          <div className="flex min-h-[72px] items-center justify-between gap-3 px-4 sm:px-6 xl:px-8">
            <div className="flex min-w-0 items-center gap-3">
              <button aria-label="Open navigation" className="rounded-lg border bg-white p-2 text-slate-600 hover:bg-slate-50 lg:hidden" onClick={() => setMobileNavigationOpen(true)}><Menu size={18} /></button>
              <div className="min-w-0"><div className="hidden items-center gap-2 text-[11px] text-slate-400 sm:flex"><span>TradeDesk</span><span>/</span><span>Workspace</span><span>/</span><span className="font-medium text-slate-600">{pageTitle}</span></div><h1 className="mt-0.5 truncate text-base font-bold tracking-tight sm:text-lg">{pageTitle}</h1></div>
            </div>
            <div className="flex items-center gap-2 sm:gap-3">
              <label className="hidden min-w-0 items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 md:flex xl:min-w-[250px]">
                <Building2 size={15} className="shrink-0 text-slate-400" />
                <select value={selectedOrganizationId} onChange={(event) => setSelectedOrganizationId(event.target.value)} aria-label="Active organization" className="min-w-0 flex-1 bg-transparent text-xs font-semibold text-slate-700 outline-none" disabled={organizations.length === 0}>
                  {organizations.length === 0 ? <option value="">No organization</option> : organizations.map((organization) => <option key={organization.organization_id} value={organization.organization_id}>{organization.organization_name}</option>)}
                </select>
                <ChevronDown size={14} className="text-slate-400" />
              </label>
              <Link to="/app/notifications" aria-label={`Notifications${unreadCount ? `, ${unreadCount} unread` : ''}`} title="Notifications" className="relative rounded-lg border border-slate-200 bg-white p-2.5 text-slate-600 hover:bg-slate-50"><Bell size={17} />{unreadCount > 0 && <span className="absolute -right-1 -top-1 flex min-h-4 min-w-4 items-center justify-center rounded-full bg-rose-600 px-1 text-[9px] font-bold text-white">{unreadCount > 99 ? '99+' : unreadCount}</span>}</Link>
              <div className="hidden h-8 w-px bg-slate-200 sm:block" />
              <div className="hidden text-right sm:block"><p className="max-w-40 truncate text-xs font-semibold text-slate-800">{auth?.user.full_name}</p><p className="max-w-40 truncate text-[10px] text-slate-500">{auth?.user.email}</p></div>
              <span aria-hidden="true" className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-900 text-xs font-bold text-white">{auth?.user.full_name.split(/\s+/).slice(0, 2).map((part) => part[0]).join('').toUpperCase()}</span>
              <Button variant="ghost" size="icon" aria-label="Sign out" title="Sign out" onClick={onLogout}><LogOut size={17} /></Button>
            </div>
          </div>
          <div className="border-t border-slate-100 px-4 py-2 md:hidden">
            <label className="flex items-center gap-2 text-xs font-medium text-slate-500">
              <Building2 size={14} aria-hidden="true" />
              <span className="shrink-0">Organization</span>
              <select value={selectedOrganizationId} onChange={(event) => setSelectedOrganizationId(event.target.value)} aria-label="Active organization" className="min-w-0 flex-1 rounded-md bg-slate-50 px-2 py-1.5 font-semibold text-slate-700 outline-none" disabled={organizations.length === 0}>
                {organizations.length === 0 ? <option value="">No organization</option> : organizations.map((organization) => <option key={organization.organization_id} value={organization.organization_id}>{organization.organization_name}</option>)}
              </select>
            </label>
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1600px] px-4 py-6 sm:px-6 sm:py-8 xl:px-8">
          <Outlet context={{ selectedOrganizationId, setSelectedOrganizationId, selectedOrganization } satisfies AppShellOutletContext} />
        </main>
      </div>
    </div>
  )
}
