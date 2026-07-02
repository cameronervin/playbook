import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import RootRedirect from '@/src/app/page'
import { useCurrentUser } from '@/src/hooks/useAuth'
import type { CurrentUser } from '@/src/types/auth'

const replace = vi.fn()

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace }),
}))

vi.mock('@/src/hooks/useAuth', () => ({
  useCurrentUser: vi.fn(),
}))

const mockUseCurrentUser = vi.mocked(useCurrentUser)

function mockCurrentUser(returnValue: { data?: CurrentUser; isLoading?: boolean; isError?: boolean }) {
  mockUseCurrentUser.mockReturnValue({
    data: returnValue.data,
    isLoading: returnValue.isLoading ?? false,
    isError: returnValue.isError ?? false,
  } as ReturnType<typeof useCurrentUser>)
}

function renderWithQuery(ui: React.ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

describe('RootRedirect', () => {
  beforeEach(() => {
    replace.mockReset()
    mockUseCurrentUser.mockReset()
  })

  it('sends unauthenticated users to login', async () => {
    mockCurrentUser({ isError: true })
    renderWithQuery(<RootRedirect />)

    await waitFor(() => expect(replace).toHaveBeenCalledWith('/login'))
  })

  it('sends incomplete athletes to profile', async () => {
    mockCurrentUser({
      data: {
        id: 'user-1',
        organization_id: 'org-1',
        email: 'athlete@example.com',
        name: 'Jordan',
        role: 'athlete',
        profile_complete: false,
        is_active: true,
      },
    })
    renderWithQuery(<RootRedirect />)

    await waitFor(() => expect(replace).toHaveBeenCalledWith('/profile'))
  })

  it('sends admins to admin', async () => {
    mockCurrentUser({
      data: {
        id: 'user-1',
        organization_id: 'org-1',
        email: 'admin@example.com',
        name: 'Jordan',
        role: 'super_admin',
        profile_complete: true,
        is_active: true,
      },
    })
    renderWithQuery(<RootRedirect />)

    await waitFor(() => expect(replace).toHaveBeenCalledWith('/admin'))
  })

  it('renders a branded loading state while resolving auth', async () => {
    mockCurrentUser({ isLoading: true })
    renderWithQuery(<RootRedirect />)

    expect(screen.getByTestId('playbook-brand-loader')).toBeInTheDocument()
    expect(screen.getByRole('status', { name: /loading playbook/i })).toBeInTheDocument()
    expect(screen.getByText(/^Loading$/i)).toBeInTheDocument()
    expect(screen.queryByText(/opening playbook/i)).not.toBeInTheDocument()
  })
})
