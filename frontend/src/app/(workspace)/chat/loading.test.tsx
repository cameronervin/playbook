import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import ChatLoading from './loading'

describe('Chat loading route', () => {
  it('renders the empty chat workspace skeleton without the sources panel', () => {
    render(<ChatLoading />)

    expect(screen.getByTestId('chat-workspace-skeleton')).toBeInTheDocument()
    expect(screen.getAllByTestId('chat-history-skeleton-row')).toHaveLength(5)
    expect(screen.getByTestId('chat-empty-skeleton')).toBeInTheDocument()
    expect(screen.getByTestId('chat-composer-shell')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /ask playbookai/i })).toBeInTheDocument()
    const newChat = screen.getByRole('button', { name: /new chat/i })
    const searchChats = screen.getByPlaceholderText(/search chats/i)
    const askButton = screen.getByRole('button', { name: /^ask$/i })

    expect(newChat).toHaveClass('pb-ui-sm')
    expect(newChat).toHaveClass('font-semibold')
    expect(searchChats).toHaveClass('pb-ui-sm')
    expect(newChat).not.toHaveClass('text-sm')
    expect(searchChats).toBeDisabled()
    expect(askButton).toBeDisabled()
    expect(askButton).toHaveClass('disabled:bg-surface-raised')
    expect(screen.queryByText(/get answers to your athletics questions/i)).not.toBeInTheDocument()
    expect(screen.getByText(/responses are ai generated/i)).toBeInTheDocument()
    expect(screen.queryByTestId('chat-composer-content-skeleton')).not.toBeInTheDocument()
    expect(screen.queryByTestId('chat-thread-skeleton')).not.toBeInTheDocument()
    expect(screen.queryByRole('complementary', { name: /sources/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('complementary', { name: /sources loading/i })).not.toBeInTheDocument()
    expect(screen.queryByText(/loading chat/i)).not.toBeInTheDocument()
  })
})
