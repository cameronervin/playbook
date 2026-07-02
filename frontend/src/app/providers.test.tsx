import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Providers } from '@/src/app/providers'
import { ApiError } from '@/src/lib/api/client'
import { ROUTES } from '@/src/lib/constants/config'
import { useUIStore } from '@/src/lib/store/uiStore'

const routerMocks = vi.hoisted(() => ({
  replace: vi.fn(),
}))

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: routerMocks.replace }),
}))

function ExpiringMutationButton() {
  const queryClient = useQueryClient()
  const mutation = useMutation({
    mutationFn: async () => {
      queryClient.setQueryData(['private-data'], { ok: true })
      throw new ApiError('Not authenticated', 401, {
        code: 'UNAUTHORIZED',
        details: { reason: 'session_expired' },
        retryable: false,
      })
    },
    retry: false,
  })
  return <button onClick={() => mutation.mutate()} type="button">Expire session</button>
}

describe('Providers auth expiry handling', () => {
  beforeEach(() => {
    routerMocks.replace.mockReset()
    useUIStore.getState().resetSessionState()
  })

  it('clears session UI state and redirects when a mutation fails with an expired session', async () => {
    const user = userEvent.setup({ delay: null })
    useUIStore.setState({
      activeConversationId: 'conversation-1',
      adminChatOpen: true,
      settingsOpen: true,
      sourcesOpen: true,
    })
    render(
      <Providers>
        <ExpiringMutationButton />
      </Providers>,
    )

    await user.click(screen.getByRole('button', { name: /expire session/i }))

    await waitFor(() =>
      expect(routerMocks.replace).toHaveBeenCalledWith(`${ROUTES.login}?reason=session_expired`),
    )
    expect(useUIStore.getState().activeConversationId).toBeNull()
    expect(useUIStore.getState().adminChatOpen).toBe(false)
    expect(useUIStore.getState().settingsOpen).toBe(false)
    expect(useUIStore.getState().sourcesOpen).toBe(false)
  })
})
