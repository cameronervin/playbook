import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { LoginScreen } from '@/src/components/features/login/LoginScreen'

vi.mock('@/src/hooks/useAuth', () => ({
  useAuthProviders: () => ({
    data: {
      providers: [
        { provider: 'google', label: 'Google', enabled: true, login_url: '/api/v1/auth/google/login' },
        { provider: 'microsoft', label: 'Microsoft', enabled: true, login_url: '/api/v1/auth/microsoft/login' },
      ],
    },
    isLoading: false,
    isError: false,
  }),
  useStartOAuthLogin: () => ({
    mutateAsync: vi.fn(async (provider: string) => ({
      authorization_url: `https://oauth.example/${provider}`,
    })),
    isPending: false,
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
  it('renders Microsoft before Google with SSO-only controls', () => {
    renderLogin()
    const buttons = screen.getAllByRole('button')

    expect(buttons[0]).toHaveAccessibleName(/continue with microsoft/i)
    expect(buttons[1]).toHaveAccessibleName(/continue with google/i)
    expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument()
  })

  it('navigates to the provider authorization URL', async () => {
    const navigateAuthorizationUrl = renderLogin()

    await userEvent.click(screen.getByRole('button', { name: /continue with microsoft/i }))

    expect(navigateAuthorizationUrl).toHaveBeenCalledWith('https://oauth.example/microsoft')
  })
})
