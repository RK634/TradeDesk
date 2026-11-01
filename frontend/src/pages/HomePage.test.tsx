import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { HomePage } from './HomePage'

const authState = vi.hoisted(() => ({
  auth: null as null | { user: { id: string; email: string; full_name: string; is_active: boolean; created_at: string }; organizations: [] },
  isLoading: false,
}))

vi.mock('@/features/auth/AuthProvider', () => ({ useAuth: () => authState }))

function renderPage() {
  const router = createMemoryRouter([
    { path: '/', element: <HomePage /> },
    { path: '/app', element: <div>Authenticated workspace</div> },
  ], { initialEntries: ['/'] })
  return render(<RouterProvider router={router} />)
}

describe('HomePage public experience', () => {
  afterEach(() => {
    authState.auth = null
    authState.isLoading = false
  })

  it('explains the TradeDesk product and its business workflows without technical environment details', () => {
    renderPage()

    expect(screen.getByRole('heading', { name: /Manage every trade, from order to settlement/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'What you can manage' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'How TradeDesk works' })).toBeInTheDocument()
    expect(screen.getByText('Import and export orders')).toBeInTheDocument()
    expect(screen.queryByText(/Environment status/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/PostgreSQL/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/Explore API docs/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/Phase \d+/i)).not.toBeInTheDocument()
  })

  it('redirects an authenticated user directly to the workspace', async () => {
    authState.auth = {
      user: { id: 'user-1', email: 'owner@example.com', full_name: 'Test Owner', is_active: true, created_at: '2026-10-01T00:00:00Z' },
      organizations: [],
    }

    renderPage()

    expect(await screen.findByText('Authenticated workspace')).toBeInTheDocument()
  })
})
