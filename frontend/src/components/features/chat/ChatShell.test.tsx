import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ChatShell } from '@/src/components/features/chat/ChatShell'

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}))

vi.mock('@/src/hooks/useAuth', () => ({
  useCurrentUser: () => ({
    data: {
      name: 'Jordan Athlete',
      email: 'athlete@example.com',
      role: 'athlete',
      profile_complete: true,
    },
    isLoading: false,
  }),
  useLogout: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock('@/src/hooks/useConversations', () => ({
  useConversations: () => ({ data: [], isLoading: false }),
  useCreateConversation: () => ({ mutate: vi.fn(), isPending: false }),
  useConversationDetail: () => ({ data: undefined, isLoading: false }),
}))

function renderChat() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <ChatShell />
    </QueryClientProvider>,
  )
}

describe('ChatShell', () => {
  it('renders the athlete empty state and sources panel by default', () => {
    renderChat()

    expect(screen.getByRole('heading', { name: /ask playbookai/i })).toBeInTheDocument()
    expect(screen.getByText(/grounding sources/i)).toBeInTheDocument()
  })

  it('toggles the sources panel', async () => {
    renderChat()

    await userEvent.click(screen.getByRole('button', { name: /toggle sources/i }))

    expect(screen.queryByText(/grounding sources/i)).not.toBeInTheDocument()
  })
})
