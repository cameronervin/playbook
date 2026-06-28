import { API_URL } from '@/src/lib/constants/config'

export const AUTH_EXPIRED_EVENT = 'playbook:auth-expired'

export interface StructuredError {
  code: string
  message: string
  retryable: boolean
  details: Record<string, unknown>
}

interface ErrorEnvelope {
  error?: Partial<StructuredError>
}

export class ApiError extends Error {
  public readonly code: string
  public readonly retryable: boolean
  public readonly details: Record<string, unknown>

  constructor(message: string, status: number, error?: Partial<StructuredError>) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = error?.code ?? 'UNKNOWN_ERROR'
    this.retryable = error?.retryable ?? false
    this.details = error?.details ?? {}
  }

  public readonly status: number
}

interface RequestOptions extends RequestInit {
  json?: unknown
}

const parseError = async (response: Response): Promise<Partial<StructuredError>> => {
  const fallback = {
    code: 'UNKNOWN_ERROR',
    message: `Request failed: ${response.statusText}`,
    retryable: false,
    details: {},
  }
  try {
    const payload = (await response.json()) as ErrorEnvelope
    return { ...fallback, ...payload.error }
  } catch {
    return fallback
  }
}

export function isAuthExpiredError(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401 && error.code === 'UNAUTHORIZED'
}

function emitAuthExpired(error: ApiError): void {
  if (typeof window === 'undefined') return
  window.dispatchEvent(
    new CustomEvent(AUTH_EXPIRED_EVENT, {
      detail: {
        code: error.code,
        reason: error.details.reason,
        status: error.status,
      },
    }),
  )
}

export async function apiClient<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { json, headers, body, ...rest } = options
  const requestHeaders: Record<string, string> = {}
  new Headers(headers).forEach((value, key) => {
    requestHeaders[key] = value
  })

  let requestBody = body
  if (json !== undefined) {
    requestBody = JSON.stringify(json)
    requestHeaders['Content-Type'] = 'application/json'
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...rest,
    credentials: 'include',
    headers: requestHeaders,
    body: requestBody,
  })

  if (!response.ok) {
    const error = await parseError(response)
    const apiError = new ApiError(error.message ?? `Request failed: ${response.statusText}`, response.status, error)
    if (isAuthExpiredError(apiError)) emitAuthExpired(apiError)
    throw apiError
  }

  if (response.status === 204) {
    return undefined as T
  }

  const text = await response.text()
  if (!text) {
    return undefined as T
  }

  return JSON.parse(text) as T
}
