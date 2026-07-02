import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import ChatPage from './page'

vi.mock('@/src/components/features/chat/ChatShell', () => ({
  ChatShell: () => <div>Chat shell from workspace group</div>,
}))

describe('Workspace chat route', () => {
  it('renders the chat shell without changing the public URL segment', () => {
    render(<ChatPage />)

    expect(screen.getByText(/chat shell from workspace group/i)).toBeInTheDocument()
  })
})
