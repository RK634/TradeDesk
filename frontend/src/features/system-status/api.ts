import type { ReadinessResponse } from './types'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '')

export async function getReadiness(): Promise<ReadinessResponse> {
  const response = await fetch(`${API_BASE_URL}/health/ready`, {
    headers: { Accept: 'application/json' },
  })

  if (!response.ok) {
    throw new Error(response.status === 503 ? 'The API is running, but the database is not ready.' : 'Unable to reach the API.')
  }

  return (await response.json()) as ReadinessResponse
}
