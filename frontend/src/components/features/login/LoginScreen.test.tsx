import { beforeEach, describe, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { LoginScreen } from '@/src/components/features/login/LoginScreen'
import type { AuthProvider } from '@/src/types/auth'

const authMocks = vi.hoisted(() => ({
  isError: false,
  isPending: false,
  mutateAsync: vi.fn(async (request: { provider: string; persona?: string }) => ({
    authorization_url: request.persona
      ? `https://oauth.example/${request.provider}/${request.persona}`
      : `https://oauth.example/${request.provider}`,
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

const globalsCss = readFileSync(resolve(process.cwd(), 'src/app/globals.css'), 'utf8')

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

    expect(screen.getByTestId('auth-card')).toBeInTheDocument()
    expect(buttons[0]).toHaveAccessibleName(/continue with microsoft/i)
    expect(buttons[1]).toHaveAccessibleName(/continue with google/i)
    expect(buttons[0]).toHaveClass('pb-auth-provider-button')
    expect(buttons[1]).toHaveClass('pb-auth-provider-button')
    expect(buttons[0].querySelector('.pb-auth-provider-icon')).toBeInTheDocument()
    expect(buttons[1].querySelector('.pb-auth-provider-icon')).toBeInTheDocument()
    expect(microsoftLabel).toHaveClass('pb-auth-provider-label')
    expect(googleLabel).toHaveClass('pb-auth-provider-label')
    expect(screen.getByRole('heading', { name: 'Log in to continue' })).toHaveClass('pb-auth-heading')
    expect(screen.getByRole('heading', { name: 'Log in to continue' })).toHaveTextContent('Log in to continue')
    expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/can't log in/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/all systems operational/i)).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: /privacy policy/i })).toHaveAttribute('href', '/privacy')
    expect(screen.getByRole('link', { name: /terms of service/i })).toHaveAttribute('href', '/terms')
  })

  it('renders a session-expired message when redirected after inactivity', () => {
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <LoginScreen sessionExpired navigateAuthorizationUrl={vi.fn()} />
      </QueryClientProvider>,
    )

    expect(screen.getByText(/your session expired after a period of inactivity/i)).toBeInTheDocument()
  })

  it('keeps provider logos centered in fixed tile cells', () => {
    renderLogin()
    const microsoftButton = screen.getByRole('button', { name: /continue with microsoft/i })
    const googleButton = screen.getByRole('button', { name: /continue with google/i })
    const microsoftIcon = microsoftButton.querySelector('.pb-auth-provider-icon')
    const googleIcon = googleButton.querySelector('.pb-auth-provider-icon')

    expect(microsoftIcon).toContainElement(microsoftIcon?.querySelector('svg') ?? null)
    expect(googleIcon).toContainElement(googleIcon?.querySelector('svg') ?? null)
    expect(globalsCss).toMatch(/\.pb-auth-provider-icon\s*{[^}]*display:\s*grid;/s)
    expect(globalsCss).toMatch(/\.pb-auth-provider-icon\s*{[^}]*height:\s*var\(--spacing-auth-provider-icon\);/s)
    expect(globalsCss).toMatch(/\.pb-auth-provider-icon\s*{[^}]*padding-bottom:\s*0;/s)
    expect(globalsCss).toMatch(/\.pb-auth-provider-icon\s*{[^}]*place-items:\s*center;/s)
    expect(globalsCss).toMatch(/\.pb-auth-provider-icon\s*{[^}]*transition:\s*background var\(--dur-fast\) var\(--ease-out\);/s)
    expect(globalsCss).toMatch(/\.pb-auth-provider-icon\s+svg\s*{[^}]*display:\s*block;/s)
    expect(globalsCss).toMatch(
      /\.pb-auth-provider-button:hover:not\(:disabled\)\s+\.pb-auth-provider-icon\s*{[^}]*background:\s*var\(--surface-hover\);/s,
    )
    expect(globalsCss).toMatch(/\.pb-auth-provider-label\s*{[^}]*justify-content:\s*flex-start;/s)
    expect(globalsCss).toMatch(/\.pb-auth-provider-label\s*{[^}]*text-align:\s*left;/s)
  })

  it('navigates to the provider authorization URL', async () => {
    const navigateAuthorizationUrl = renderLogin()

    await userEvent.click(screen.getByRole('button', { name: /continue with microsoft/i }))

    expect(navigateAuthorizationUrl).toHaveBeenCalledWith('https://oauth.example/microsoft')
  })

  it('renders Developer SSO last when the local provider is returned', async () => {
    authMocks.providers = [
      { provider: 'google', label: 'Google', enabled: true, login_url: '/api/v1/auth/google/login' },
      { provider: 'dev', label: 'Developer SSO', enabled: true, login_url: '/api/v1/auth/dev/login' },
      { provider: 'microsoft', label: 'Microsoft', enabled: true, login_url: '/api/v1/auth/microsoft/login' },
    ]
    const navigateAuthorizationUrl = renderLogin()
    const buttons = screen.getAllByRole('button')

    expect(buttons.map((button) => button.textContent)).toEqual([
      'Continue with Microsoft',
      'Continue with Google',
      'Continue with Developer SSO',
    ])
    expect(buttons[2]).toHaveClass('pb-auth-provider-button')
    expect(buttons[2].querySelector('.pb-auth-provider-icon')).toBeInTheDocument()
    expect(buttons[2].querySelector('.pb-auth-provider-label')).toHaveTextContent('Continue with Developer SSO')

    await userEvent.click(screen.getByRole('button', { name: /continue with developer sso/i }))

    await userEvent.click(screen.getByRole('menuitem', { name: 'Admin' }))

    expect(authMocks.mutateAsync).toHaveBeenCalledWith({ provider: 'dev', persona: 'admin' })
    expect(navigateAuthorizationUrl).toHaveBeenCalledWith('https://oauth.example/dev/admin')
  })

  it('shows all Developer SSO personas and starts login for each selected role', async () => {
    authMocks.providers = [
      { provider: 'dev', label: 'Developer SSO', enabled: true, login_url: '/api/v1/auth/dev/login' },
    ]
    const navigateAuthorizationUrl = renderLogin()
    const user = userEvent.setup()

    await user.click(screen.getByRole('button', { name: /continue with developer sso/i }))

    expect(screen.getByRole('menuitem', { name: 'Athlete' })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: 'New athlete' })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: 'Admin' })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: 'Super admin' })).toBeInTheDocument()

    await user.click(screen.getByRole('menuitem', { name: 'Athlete' }))
    expect(authMocks.mutateAsync).toHaveBeenLastCalledWith({ provider: 'dev', persona: 'athlete' })
    expect(navigateAuthorizationUrl).toHaveBeenLastCalledWith('https://oauth.example/dev/athlete')

    await user.click(screen.getByRole('button', { name: /continue with developer sso/i }))
    await user.click(screen.getByRole('menuitem', { name: 'New athlete' }))
    expect(authMocks.mutateAsync).toHaveBeenLastCalledWith({ provider: 'dev', persona: 'new_athlete' })
    expect(navigateAuthorizationUrl).toHaveBeenLastCalledWith('https://oauth.example/dev/new_athlete')

    await user.click(screen.getByRole('button', { name: /continue with developer sso/i }))
    await user.click(screen.getByRole('menuitem', { name: 'Super admin' }))
    expect(authMocks.mutateAsync).toHaveBeenLastCalledWith({ provider: 'dev', persona: 'super_admin' })
    expect(navigateAuthorizationUrl).toHaveBeenLastCalledWith('https://oauth.example/dev/super_admin')
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
    expect(screen.getByRole('button', { name: /continue with microsoft/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /continue with google/i })).toBeDisabled()
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
