import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ProfileScreen } from '@/src/components/features/profile/ProfileScreen'

const push = vi.fn()
const mutateAsync = vi.fn()

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push }),
}))

vi.mock('@/src/hooks/useAuth', () => ({
  useCurrentUser: () => ({
    data: { name: 'Jordan Athlete', email: 'athlete@example.com' },
    isLoading: false,
  }),
}))

vi.mock('@/src/hooks/useProfile', () => ({
  useUpdateProfile: () => ({
    mutateAsync,
    isPending: false,
    error: null,
  }),
}))

function renderProfile() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <ProfileScreen />
    </QueryClientProvider>,
  )
}

describe('ProfileScreen', () => {
  it('renders profile completion inside the shared auth shell', () => {
    renderProfile()

    const authCard = screen.getByTestId('auth-card')
    const brandLockup = screen.getByText('Playbook').closest('div')
    const heading = screen.getByRole('heading', { name: /complete your profile/i })
    const description = screen.getByText(/add the basics playbook needs/i)
    const nameField = screen.getByLabelText(/name/i)
    const sportField = screen.getByLabelText(/sport or team/i)
    const continueButton = screen.getByRole('button', { name: /let's get started/i })

    expect(authCard).toBeInTheDocument()
    expect(authCard).not.toHaveClass('pb-auth-card-wide')
    expect(brandLockup).toHaveClass('justify-center')
    expect(heading).toHaveClass('text-lg')
    expect(heading).not.toHaveClass('text-[28px]')
    expect(description).toHaveClass('text-sm')
    expect(description).not.toHaveClass('text-base')
    expect(nameField).toHaveClass('min-h-[52px]')
    expect(nameField).not.toHaveClass('min-h-16')
    expect(sportField).toHaveAttribute('placeholder', 'Basketball')
    expect(sportField).toHaveClass('min-h-[52px]')
    expect(continueButton).toHaveClass('w-full', 'min-h-[52px]')
    expect(continueButton).not.toHaveClass('min-h-16')
  })

  it('submits athlete profile completion and follows next route', async () => {
    mutateAsync.mockResolvedValueOnce({ next_route: '/chat' })
    renderProfile()

    await userEvent.clear(screen.getByLabelText(/name/i))
    await userEvent.type(screen.getByLabelText(/name/i), 'Jordan Athlete')
    await userEvent.type(screen.getByLabelText(/sport/i), 'Basketball')
    await userEvent.click(screen.getByRole('button', { name: /let's get started/i }))

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith({
        name: 'Jordan Athlete',
        sport_team: 'Basketball',
        selected_role: 'athlete',
      })
      expect(push).toHaveBeenCalledWith('/chat')
    })
  })
})
