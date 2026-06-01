import { API_URL } from '@/lib/constants/config'

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

interface RequestOptions extends RequestInit {
  json?: unknown
}

/**
 * Thin typed fetch wrapper around the backend API.
 * Prefixes the configured API base URL and parses JSON responses.
 */
export async function apiClient<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { json, headers, ...rest } = options

  const response = await fetch(`${API_URL}${path}`, {
    ...rest,
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  })

  if (!response.ok) {
    throw new ApiError(`Request failed: ${response.statusText}`, response.status)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}
