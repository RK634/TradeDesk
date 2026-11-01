import { createContext, useContext, useEffect, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, getCurrentUser, loginRequest, logoutRequest, registerRequest } from './api'
import type { AuthMe, AuthResult } from './types'

const AUTH_QUERY_KEY = ['auth', 'me'] as const

interface AuthContextValue {
  auth: AuthMe | null
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (input: { email: string; full_name: string; password: string; organization_name: string }) => Promise<void>
  logout: () => Promise<void>
  refresh: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

function authMeFromResult(result: AuthResult): AuthMe {
  return { user: result.user, organizations: result.organizations }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  useEffect(() => {
    const handleUnauthorized = () => queryClient.setQueryData<AuthMe | null>(AUTH_QUERY_KEY, null)
    window.addEventListener('auth:unauthorized', handleUnauthorized)
    return () => window.removeEventListener('auth:unauthorized', handleUnauthorized)
  }, [queryClient])

  const currentUserQuery = useQuery<AuthMe | null>({
    queryKey: AUTH_QUERY_KEY,
    queryFn: async () => {
      try {
        return await getCurrentUser()
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) return null
        throw error
      }
    },
    retry: false,
    staleTime: 15_000,
  })

  async function login(email: string, password: string) {
    const result = await loginRequest(email, password)
    queryClient.setQueryData<AuthMe | null>(AUTH_QUERY_KEY, authMeFromResult(result))
  }

  async function register(input: { email: string; full_name: string; password: string; organization_name: string }) {
    const result = await registerRequest(input)
    queryClient.setQueryData<AuthMe | null>(AUTH_QUERY_KEY, authMeFromResult(result))
  }

  async function logout() {
    try {
      await logoutRequest()
    } finally {
      queryClient.setQueryData<AuthMe | null>(AUTH_QUERY_KEY, null)
      await queryClient.invalidateQueries({ queryKey: ['organization-members'] })
    }
  }

  async function refresh() {
    // Invalidating the active query also triggers a refetch, avoiding duplicate requests.
    await queryClient.invalidateQueries({ queryKey: AUTH_QUERY_KEY })
  }

  return (
    <AuthContext.Provider value={{
      auth: currentUserQuery.data ?? null,
      isLoading: currentUserQuery.isPending,
      login,
      register,
      logout,
      refresh,
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside AuthProvider.')
  return context
}
