import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { LoginScreen } from '@/src/components/features/login/LoginScreen'
import type { AuthProvider } from '@/src/types/auth'

const authMocks = vi.hoisted(() => ({
  isError: false,
  isPending: false,
  mutateAsync: vi.fn(async (provider: string) => ({
    authorization_url: `https://oauth.example/${provider}`,
  })),
  providers: [
    { provider: 'google', label: 'Google', enabled: true, login_url: '/api/v1/auth/google/login' },
    { provider: 'microsoft', label: 'Microsoft', enabled: true, login_url: '/api/v1/auth/microsoft/login' },
  ] as AuthProvider[] | undefined,
}))

vi.mock('@/src/hooks/useAuth', () => ({
  useAuthProviders: () => ({
    data: authMocks.providers ? { providers: authMocks.providers } : undefined,
    isError: authMocks.isError,
    isPending: authMocks.isPending,
  }),
  useStartOAuthLogin: () => ({
    mutateAsync: authMocks.mutateAsync,
    isPending: authMocks.isPending,
  }),
}))

function renderLogin(navigateAuthorizationUrl = vi.fn()) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <LoginScreen navigateAuthorizationUrl={navigateAuthorizationUrl} />
    </QueryClientProvider>,
  )
  return navigateAuthorizationUrl
}

describe('LoginScreen', () => {
  beforeEach(() => {
    authMocks.isError = false
    authMocks.isPending = false
    authMocks.mutateAsync.mockClear()
    authMocks.providers = [
      { provider: 'google', label: 'Google', enabled: true, login_url: '/api/v1/auth/google/login' },
      { provider: 'microsoft', label: 'Microsoft', enabled: true, login_url: '/api/v1/auth/microsoft/login' },
    ]
  })

  it('renders Microsoft before Google with SSO-only controls', () => {
    renderLogin()
    const buttons = screen.getAllByRole('button')
    const microsoftLabel = screen.getByText('Continue with Microsoft')
    const googleLabel = screen.getByText('Continue with Google')

    expect(buttons[0]).toHaveAccessibleName(/continue with microsoft/i)
    expect(buttons[1]).toHaveAccessibleName(/continue with google/i)
    expect(microsoftLabel).toHaveClass('justify-start', 'pl-8')
    expect(googleLabel).toHaveClass('justify-start', 'pl-8')
    expect(screen.getByRole('heading', { name: 'Log in to continue' })).toHaveTextContent('LOG IN TO CONTINUE')
    expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/can't log in/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/all systems operational/i)).not.toBeInTheDocument()
    expect(screen.getByTestId('login-stage')).not.toHaveClass('pb-ambient-grid')
  })

  it('navigates to the provider authorization URL', async () => {
    const navigateAuthorizationUrl = renderLogin()

    await userEvent.click(screen.getByRole('button', { name: /continue with microsoft/i }))

    expect(navigateAuthorizationUrl).toHaveBeenCalledWith('https://oauth.example/microsoft')
  })

  it('does not start OAuth when a provider is disabled', async () => {
    authMocks.providers = [
      { provider: 'google', label: 'Google', enabled: true, login_url: '/api/v1/auth/google/login' },
      { provider: 'microsoft', label: 'Microsoft', enabled: false, login_url: '/api/v1/auth/microsoft/login' },
    ]
    const navigateAuthorizationUrl = renderLogin()

    await userEvent.click(screen.getByRole('button', { name: /continue with microsoft/i }))

    expect(authMocks.mutateAsync).not.toHaveBeenCalled()
    expect(navigateAuthorizationUrl).not.toHaveBeenCalled()
  })

  it('renders provider skeleton tiles during the first uncached provider load', () => {
    authMocks.isPending = true
    authMocks.providers = undefined

    renderLogin()

    expect(screen.getAllByTestId('auth-provider-skeleton')).toHaveLength(2)
    expect(screen.queryByText(/checking available providers/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /continue with microsoft/i })).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument()
  })

  it('renders cached provider buttons instead of skeletons during background refetch states', () => {
    authMocks.isPending = true

    renderLogin()

    expect(screen.queryByTestId('auth-provider-skeleton')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /continue with microsoft/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /continue with google/i })).toBeInTheDocument()
  })

  it('renders provider errors only when there is no cached provider data', () => {
    authMocks.isError = true
    authMocks.providers = undefined

    renderLogin()

    expect(screen.getByText(/sso providers are not available right now/i)).toBeInTheDocument()
  })

  it('keeps cached provider buttons visible when a background provider refetch errors', () => {
    authMocks.isError = true

    renderLogin()

    expect(screen.queryByText(/sso providers are not available right now/i)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /continue with microsoft/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /continue with google/i })).toBeInTheDocument()
  })
})
