import { fireEvent, render, screen } from '@testing-library/react'
import type { ComponentProps } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { AdminChatPanel } from '@/src/components/features/admin/AdminChatPanel'
import type { AdminChatMessage } from '@/src/types/adminChat'

function adminMessage(overrides: Partial<AdminChatMessage> = {}): AdminChatMessage {
  return {
    id: 'admin-assistant-1',
    session_id: 'admin-chat-session-1',
    role: 'assistant',
    content: '',
    status: 'streaming',
    references: [],
    metadata: {},
    answer_type: null,
    created_at: '2026-07-01T12:00:00Z',
    ...overrides,
  }
}

function renderPanel(
  props: Partial<ComponentProps<typeof AdminChatPanel>> = {},
) {
  return render(
    <AdminChatPanel
      messages={[]}
      onClose={vi.fn()}
      onSend={vi.fn()}
      {...props}
    />,
  )
}

describe('AdminChatPanel', () => {
  it('uses the shared rounded composer focus shell', () => {
    renderPanel()

    const composer = screen.getByLabelText(/message analytics ai/i).closest('.pb-chat-composer-shell')

    expect(composer).toHaveClass('pb-field-shell')
    expect(composer).toHaveClass('pb-chat-composer-shell')
  })

  it('uses the shared side-panel header rhythm', () => {
    const { container } = renderPanel()

    const header = screen.getByRole('heading', { name: /analytics ai agent/i }).closest('header')

    expect(header).toHaveClass('pb-panel-header')
    expect(header).not.toHaveClass('pb-admin-chat-panel-header')
    expect(header?.querySelector('.lucide-zap')).not.toBeInTheDocument()
    expect(header?.querySelector('.lucide-bot-message-square')).not.toBeInTheDocument()
    expect(container.querySelector('.lucide-bot-message-square')).not.toBeInTheDocument()
  })

  it('renders an optimistic pending user turn with exactly one shimmer indicator', () => {
    const { container } = renderPanel({
      isBusy: true,
      pendingMessage: 'What support gaps changed this week?',
    })

    expect(screen.getByText('What support gaps changed this week?')).toBeInTheDocument()
    expect(screen.getAllByText('Thinking...')).toHaveLength(1)
    expect(screen.getByText('Thinking...')).toHaveClass('pb-thinking-shimmer')
    expect(container.querySelector('.pb-think')).not.toBeInTheDocument()
  })

  it('renders streamed assistant content without the thinking shimmer', () => {
    renderPanel({
      messages: [
        adminMessage({
          content: 'NIL questions are rising in the last seven days.',
          status: 'streaming',
        }),
      ],
    })

    expect(screen.getByText(/NIL questions are rising/i)).toBeInTheDocument()
    expect(screen.queryByText('Thinking...')).not.toBeInTheDocument()
  })

  it('renders empty streaming assistant messages with the shared shimmer', () => {
    renderPanel({
      messages: [
        adminMessage({
          content: '',
          status: 'streaming',
        }),
      ],
    })

    expect(screen.getByText('Thinking...')).toHaveClass('pb-thinking-shimmer')
  })

  it('does not render admin source chips from backend references', () => {
    renderPanel({
      messages: [
        adminMessage({
          content: 'Compliance flags are concentrated around NIL disclosure timing.',
          references: [
            {
              id: '54da3d0c-4b77-44c2-a472-91be2d9c6720',
              type: 'query',
            },
          ],
          status: 'complete',
        }),
      ],
    })

    expect(screen.getByText(/Compliance flags are concentrated/i)).toBeInTheDocument()
    expect(screen.queryByText('54da3d0c-4b77-44c2-a472-91be2d9c6720')).not.toBeInTheDocument()
    expect(screen.queryByText(/^Query$/i)).not.toBeInTheDocument()
  })

  it('uses the AI agent icon in assistant chat history only', () => {
    const { container } = renderPanel({
      messages: [
        adminMessage({
          content: 'NIL questions are rising in the last seven days.',
          status: 'complete',
        }),
      ],
    })

    const header = screen.getByRole('heading', { name: /analytics ai agent/i }).closest('header')
    const agentIcon = container.querySelector('.lucide-bot-message-square')

    expect(agentIcon).toBeInTheDocument()
    expect(header?.querySelector('.lucide-bot-message-square')).not.toBeInTheDocument()
  })

  it('preserves scroll position without rendering a jump-to-latest control when streaming grows after the user scrolls up', () => {
    const { rerender } = renderPanel({
      messages: [
        adminMessage({
          content: 'Start of the analytics response.',
          status: 'streaming',
        }),
      ],
    })
    const thread = screen.getByTestId('admin-chat-thread-scroll')
    const metrics = mockScrollMetrics(thread, {
      clientHeight: 500,
      scrollHeight: 1_000,
      scrollTop: 250,
    })

    fireEvent.scroll(thread)
    metrics.set({ scrollHeight: 1_200 })
    rerender(
      <AdminChatPanel
        messages={[
          adminMessage({
            content: 'Start of the analytics response. More streamed detail.',
            status: 'streaming',
          }),
        ]}
        onClose={vi.fn()}
        onSend={vi.fn()}
      />,
    )

    expect(metrics.scrollTop).toBe(250)
    expect(screen.queryByRole('button', { name: /jump to latest message/i })).not.toBeInTheDocument()
  })
})

interface ScrollMetrics {
  clientHeight: number
  scrollHeight: number
  scrollTop: number
}

function mockScrollMetrics(element: HTMLElement, initialMetrics: ScrollMetrics) {
  const metrics = { ...initialMetrics }

  Object.defineProperties(element, {
    clientHeight: {
      configurable: true,
      get: () => metrics.clientHeight,
    },
    scrollHeight: {
      configurable: true,
      get: () => metrics.scrollHeight,
    },
    scrollTop: {
      configurable: true,
      get: () => metrics.scrollTop,
      set: (value: number) => {
        metrics.scrollTop = value
      },
    },
  })

  return {
    get scrollTop() {
      return metrics.scrollTop
    },
    set: (nextMetrics: Partial<ScrollMetrics>) => {
      Object.assign(metrics, nextMetrics)
    },
  }
}
