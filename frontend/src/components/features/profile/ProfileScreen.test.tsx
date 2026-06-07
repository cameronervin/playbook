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
  it('submits athlete profile completion and follows next route', async () => {
    mutateAsync.mockResolvedValueOnce({ next_route: '/chat' })
    renderProfile()

    await userEvent.clear(screen.getByLabelText(/name/i))
    await userEvent.type(screen.getByLabelText(/name/i), 'Jordan Athlete')
    await userEvent.type(screen.getByLabelText(/sport/i), 'Basketball')
    await userEvent.click(screen.getByRole('button', { name: /continue to chat/i }))

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
