import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from './AuthProvider'

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { auth, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <main className="flex min-h-screen items-center justify-center px-6">
        <div className="rounded-xl border bg-white px-6 py-5 text-sm text-muted-foreground shadow-sm" role="status">
          Checking your secure session…
        </div>
      </main>
    )
  }

  if (!auth) return <Navigate to="/login" replace state={{ from: location }} />
  return children
}
