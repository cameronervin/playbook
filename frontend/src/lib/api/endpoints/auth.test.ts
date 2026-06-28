import { beforeEach, describe, expect, it, vi } from 'vitest'
import { startOAuthLogin } from '@/src/lib/api/endpoints/auth'
import { apiClient } from '@/src/lib/api/client'

vi.mock('@/src/lib/api/client', () => ({
  apiClient: vi.fn(),
}))

describe('auth endpoints', () => {
  beforeEach(() => {
    vi.mocked(apiClient).mockReset()
  })

  it('starts Developer SSO with the selected persona query', async () => {
    vi.mocked(apiClient).mockResolvedValueOnce({ authorization_url: 'https://oauth.example/dev/admin' })

    await startOAuthLogin({ provider: 'dev', persona: 'admin' })

    expect(apiClient).toHaveBeenCalledWith('/api/v1/auth/dev/login?persona=admin')
  })

  it('starts non-dev OAuth without a persona query', async () => {
    vi.mocked(apiClient).mockResolvedValueOnce({ authorization_url: 'https://oauth.example/microsoft' })

    await startOAuthLogin({ provider: 'microsoft' })

    expect(apiClient).toHaveBeenCalledWith('/api/v1/auth/microsoft/login')
  })

  it('does not append persona queries to non-dev providers', async () => {
    vi.mocked(apiClient).mockResolvedValueOnce({ authorization_url: 'https://oauth.example/google' })

    await startOAuthLogin({ provider: 'google', persona: 'admin' })

    expect(apiClient).toHaveBeenCalledWith('/api/v1/auth/google/login')
  })
})
