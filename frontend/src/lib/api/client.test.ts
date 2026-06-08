import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { apiClient } from '@/src/lib/api/client'

const originalFetch = global.fetch

describe('apiClient', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.stubGlobal('fetch', originalFetch)
    vi.restoreAllMocks()
  })

  it('sends credentials and JSON headers for JSON requests', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true }), { status: 200 }),
    )

    await apiClient<{ ok: boolean }>('/api/v1/example', { method: 'POST', json: { name: 'Playbook' } })

    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/example',
      expect.objectContaining({
        credentials: 'include',
        method: 'POST',
        body: JSON.stringify({ name: 'Playbook' }),
        headers: { 'Content-Type': 'application/json' },
      }),
    )
  })

  it('preserves browser multipart headers for FormData requests', async () => {
    const formData = new FormData()
    formData.append('file', new File(['hello'], 'policy.pdf', { type: 'application/pdf' }))
    vi.mocked(fetch).mockResolvedValueOnce(new Response(null, { status: 204 }))

    await apiClient<void>('/api/v1/admin/kb/documents', { method: 'POST', body: formData })

    expect(fetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/admin/kb/documents',
      expect.objectContaining({
        credentials: 'include',
        body: formData,
        headers: {},
      }),
    )
  })

  it('parses structured API errors', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          error: {
            code: 'FORBIDDEN',
            message: 'Admin role required',
            retryable: false,
            details: { request_id: 'req-1' },
          },
        }),
        { status: 403 },
      ),
    )

    await expect(apiClient('/api/v1/admin/users')).rejects.toMatchObject({
      name: 'ApiError',
      status: 403,
      code: 'FORBIDDEN',
      retryable: false,
      details: { request_id: 'req-1' },
      message: 'Admin role required',
    })
  })

  it('supports no-content responses', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response(null, { status: 204 }))

    await expect(apiClient<void>('/api/v1/auth/logout', { method: 'POST' })).resolves.toBeUndefined()
  })
})
