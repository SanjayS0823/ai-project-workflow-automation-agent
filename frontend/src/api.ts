// Typed client for the backend API.
// Requests go to the Vite dev proxy (`/api` -> backend) by default; override
// with VITE_API_BASE_URL when the backend is served elsewhere.

const API_BASE: string = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? ''

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, init)
  } catch {
    throw new ApiError(0, 'Unable to reach the server. Please try again.')
  }

  if (!response.ok) {
    let detail: string | undefined
    try {
      const body = (await response.json()) as { detail?: unknown }
      detail = typeof body.detail === 'string' ? body.detail : undefined
    } catch {
      // Non-JSON error body; fall through to the generic message.
    }
    throw new ApiError(
      response.status,
      detail ?? 'Something went wrong. Please try again.',
    )
  }

  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

export function apiGet<T>(path: string): Promise<T> {
  return request<T>(path)
}

export function apiPost<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function apiPut<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function apiDelete(path: string): Promise<void> {
  return request<void>(path, { method: 'DELETE' })
}
