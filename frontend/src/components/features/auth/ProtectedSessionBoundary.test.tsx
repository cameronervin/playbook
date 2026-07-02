import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ProtectedSessionBoundary } from '@/src/components/features/auth/ProtectedSessionBoundary'
import type { CurrentUser } from '@/src/types/auth'

const authMock = vi.hoisted((): { isLoading: boolean; user: CurrentUser | undefined } => ({
  isLoading: false,
  user: {
    id: 'user-1',
    organization_id: 'org-1',
    name: 'Jordan Athlete',
    email: 'jordan@example.com',
    role: 'athlete',
    sport_team: 'Basketball',
    profile_complete: true,
    is_active: true,
  },
}))

const useSessionActivityMock = vi.hoisted(() => vi.fn())

vi.mock('@/src/hooks/useAuth', () => ({
  useCurrentUser: () => ({
    data: authMock.user,
    isLoading: authMock.isLoading,
  }),
}))

vi.mock('@/src/hooks/useSessionActivity', () => ({
  useSessionActivity: useSessionActivityMock,
}))

describe('ProtectedSessionBoundary', () => {
  beforeEach(() => {
    authMock.isLoading = false
    authMock.user = {
      id: 'user-1',
      organization_id: 'org-1',
      name: 'Jordan Athlete',
      email: 'jordan@example.com',
      role: 'athlete',
      sport_team: 'Basketball',
      profile_complete: true,
      is_active: true,
    }
    useSessionActivityMock.mockClear()
  })

  it('renders protected children and enables session activity for a loaded user', () => {
    render(
      <ProtectedSessionBoundary>
        <p>Protected content</p>
      </ProtectedSessionBoundary>,
    )

    expect(screen.getByText('Protected content')).toBeInTheDocument()
    expect(useSessionActivityMock).toHaveBeenCalledWith({ enabled: true })
  })

  it('disables session activity while the current user is loading', () => {
    authMock.isLoading = true
    authMock.user = undefined

    render(
      <ProtectedSessionBoundary>
        <p>Loading protected content</p>
      </ProtectedSessionBoundary>,
    )

    expect(screen.getByText('Loading protected content')).toBeInTheDocument()
    expect(useSessionActivityMock).toHaveBeenCalledWith({ enabled: false })
  })

  it('disables session activity when no current user is loaded', () => {
    authMock.user = undefined

    render(
      <ProtectedSessionBoundary>
        <p>Anonymous protected content</p>
      </ProtectedSessionBoundary>,
    )

    expect(screen.getByText('Anonymous protected content')).toBeInTheDocument()
    expect(useSessionActivityMock).toHaveBeenCalledWith({ enabled: false })
  })
})
