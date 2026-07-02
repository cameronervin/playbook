import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import ProtectedLayout from './layout'
import type { ReactNode } from 'react'

vi.mock('@/src/components/features/auth/ProtectedSessionBoundary', () => ({
  ProtectedSessionBoundary: ({ children }: { children: ReactNode }) => (
    <div data-testid="protected-session-boundary">{children}</div>
  ),
}))

describe('Protected route layout', () => {
  it('wraps protected routes with the session activity boundary', () => {
    render(
      <ProtectedLayout>
        <p>Protected child content</p>
      </ProtectedLayout>,
    )

    expect(screen.getByTestId('protected-session-boundary')).toBeInTheDocument()
    expect(screen.getByText('Protected child content')).toBeInTheDocument()
  })
})
