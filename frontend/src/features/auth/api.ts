import type { AuthMe, AuthResult, InvitationPreview } from './types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export class ApiError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message)
    this.name = 'ApiError'
  }
}

function readCookie(name: string): string | null {
  if (typeof document === 'undefined') return null
  const prefix = `${encodeURIComponent(name)}=`
  const match = document.cookie.split('; ').find((entry) => entry.startsWith(prefix))
  return match ? decodeURIComponent(match.slice(prefix.length)) : null
}

async function issueCsrfToken(): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/auth/csrf`, {
    method: 'GET',
    credentials: 'include',
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) throw new ApiError('Could not initialize secure request protection.', response.status)
  const payload = (await response.json()) as { csrf_token: string }
  return payload.csrf_token
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method || 'GET').toUpperCase()
  const headers = new Headers(init.headers)
  headers.set('Accept', 'application/json')
  const isFormData = typeof FormData !== 'undefined' && init.body instanceof FormData
  if (init.body && !isFormData && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')

  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    const csrfToken = readCookie('iem_csrf') || await issueCsrfToken()
    headers.set('X-CSRF-Token', csrfToken)
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    method,
    headers,
    credentials: 'include',
  })

  if (!response.ok) {
    if (response.status === 401 && typeof window !== 'undefined') {
      window.dispatchEvent(new Event('auth:unauthorized'))
    }
    let message = `Request failed (${response.status}).`
    try {
      const payload = (await response.json()) as { detail?: unknown }
      if (typeof payload.detail === 'string') message = payload.detail
      else if (Array.isArray(payload.detail)) {
        message = payload.detail.map((item) => typeof item === 'object' && item && 'msg' in item ? String(item.msg) : 'Invalid input').join(' ')
      }
    } catch {
      // Keep the stable HTTP fallback when the server does not send JSON.
    }
    throw new ApiError(message, response.status)
  }

  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const apiGet = <T>(path: string) => request<T>(path)
export const apiPost = <T>(path: string, body?: unknown) => request<T>(path, {
  method: 'POST',
  body: body === undefined ? undefined : JSON.stringify(body),
})
export const apiPatch = <T>(path: string, body: unknown) => request<T>(path, {
  method: 'PATCH',
  body: JSON.stringify(body),
})
export const apiPut = <T>(path: string, body: unknown) => request<T>(path, {
  method: 'PUT',
  body: JSON.stringify(body),
})
export const apiDelete = <T>(path: string) => request<T>(path, { method: 'DELETE' })
export const apiUpload = <T>(path: string, body: FormData) => request<T>(path, { method: 'POST', body })
export function apiResourceUrl(path: string): string { return `${API_BASE_URL}${path}` }

export function getCurrentUser() {
  return apiGet<AuthMe>('/auth/me')
}

export function loginRequest(email: string, password: string) {
  return apiPost<AuthResult>('/auth/login', { email, password })
}

export function registerRequest(input: { email: string; full_name: string; password: string; organization_name: string }) {
  return apiPost<AuthResult>('/auth/register', input)
}

export function logoutRequest() {
  return apiPost<{ success: boolean }>('/auth/logout', {})
}

export function getInvitationPreview(token: string) {
  // Keep bearer-like invitation tokens out of URL paths and reverse-proxy access logs.
  return apiPost<InvitationPreview>('/auth/invitations/preview', { token })
}
