import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { render, screen } from '@testing-library/react'
import { createMemoryRouter, Outlet, RouterProvider } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { getDashboardSummary } from '@/features/dashboard/api'
import type { DashboardSummary } from '@/features/dashboard/types'
import { DashboardPage } from './DashboardPage'

vi.mock('@/features/auth/AuthProvider', () => ({
  useAuth: () => ({
    auth: {
      user: { id: 'user-1', email: 'owner@example.com', full_name: 'Test Owner', is_active: true, created_at: '2026-10-01T00:00:00Z' },
      organizations: [{ organization_id: 'org-1', organization_name: 'Northwind Trade', organization_slug: 'northwind-trade', membership_id: 'member-1', role: 'organization_owner', is_active: true }],
    },
  }),
}))

vi.mock('@/features/dashboard/api', () => ({ getDashboardSummary: vi.fn() }))

vi.mock('recharts', () => {
  const Container = ({ children }: { children?: ReactNode }) => <div>{children}</div>
  const Primitive = () => null
  return {
    ResponsiveContainer: Container,
    AreaChart: Container,
    BarChart: Container,
    CartesianGrid: Primitive,
    Tooltip: Primitive,
    XAxis: Primitive,
    YAxis: Primitive,
    Area: Primitive,
    Bar: Container,
    Cell: Primitive,
  }
})

const summary: DashboardSummary = {
  organization_id: 'org-1',
  organization_name: 'Northwind Trade',
  organization_role: 'organization_owner',
  period_start: '2026-10-01',
  period_end: '2026-10-30',
  generated_at: '2026-10-30T10:00:00Z',
  workspace: {
    total_members: 4,
    active_members: 3,
    inactive_members: 1,
    new_members: 2,
    pending_invitations: 2,
    can_view_invitations: true,
  },
  member_join_trend: [{ date: '2026-10-30', label: 'Oct 30', count: 2 }],
  members_by_role: [{ role: 'organization_owner', label: 'Organization owner', count: 1 }],
}

function renderDashboard() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } } })
  const outletContext = {
    selectedOrganizationId: 'org-1',
    setSelectedOrganizationId: vi.fn(),
    selectedOrganization: { organization_id: 'org-1', organization_name: 'Northwind Trade', organization_slug: 'northwind-trade', membership_id: 'member-1', role: 'organization_owner', is_active: true },
  }
  const router = createMemoryRouter([
    { path: '/app', element: <Outlet context={outletContext} />, children: [{ index: true, element: <DashboardPage /> }] },
  ], { initialEntries: ['/app'] })
  return render(<QueryClientProvider client={queryClient}><RouterProvider router={router} /></QueryClientProvider>)
}

describe('DashboardPage', () => {
  afterEach(() => vi.clearAllMocks())

  it('renders workspace metrics and practical workflow guidance without development phase labels', async () => {
    vi.mocked(getDashboardSummary).mockResolvedValue(summary)
    renderDashboard()

    expect(await screen.findByText('Active members')).toBeInTheDocument()
    expect(screen.getByText('Northwind Trade')).toBeInTheDocument()
    expect(screen.getByText('Pending invitations')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'How to use TradeDesk' })).toBeInTheDocument()
    expect(screen.getByText('Set up your workspace')).toBeInTheDocument()
    expect(screen.getByText('Create and manage an import')).toBeInTheDocument()
    expect(screen.getByText('Prepare and deliver an export')).toBeInTheDocument()
    expect(screen.queryByText(/Phase \d+/i)).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Open import orders/i })).toHaveAttribute('href', '/app/imports')
    expect(getDashboardSummary).toHaveBeenCalledWith(expect.objectContaining({ organizationId: 'org-1' }))
  })

  it('shows a retryable error when the dashboard request fails', async () => {
    vi.mocked(getDashboardSummary).mockRejectedValue(new Error('Dashboard service unavailable'))
    renderDashboard()

    expect(await screen.findByText('Dashboard data could not be loaded')).toBeInTheDocument()
    expect(screen.getByText('Dashboard service unavailable')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })
})
