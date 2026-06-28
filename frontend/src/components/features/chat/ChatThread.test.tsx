import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ChatThread } from '@/src/components/features/chat/ChatThread'
import type { ChatMessage } from '@/src/types/conversations'

function message(overrides: Partial<ChatMessage> = {}): ChatMessage {
  return {
    id: 'assistant-1',
    conversation_id: 'conversation-1',
    role: 'assistant',
    content: '',
    status: 'streaming',
    safety_outcome: null,
    topic_labels: [],
    risk_labels: [],
    metadata: {},
    citations: [],
    created_at: '2026-06-20T02:31:30Z',
    ...overrides,
  }
}

describe('ChatThread', () => {
  it('renders the pending assistant indicator with a static mark and shimmering text', () => {
    const { container } = render(
      <ChatThread
        messages={[
          message({
            content: '',
            status: 'pending',
          }),
        ]}
        onCitationSelect={vi.fn()}
      />,
    )

    expect(screen.getByText('Thinking...')).toHaveClass('pb-thinking-shimmer')
    expect(container.querySelector('.animate-pb-pulse')).not.toBeInTheDocument()
  })

  it('renders streamed assistant content before the terminal complete event', () => {
    render(
      <ChatThread
        messages={[
          message({
            content: 'Disclose the NIL deal before signing.',
            status: 'streaming',
          }),
        ]}
        onCitationSelect={vi.fn()}
      />,
    )

    expect(screen.getByText('Disclose the NIL deal before signing.')).toBeInTheDocument()
    expect(screen.queryByText('Thinking...')).not.toBeInTheDocument()
  })

  it('keeps streamed assistant content pinned when the user is near the bottom', () => {
    const { rerender } = render(
      <ChatThread
        messages={[
          message({
            content: 'Start of the streamed response.',
            status: 'streaming',
          }),
        ]}
        onCitationSelect={vi.fn()}
      />,
    )
    const thread = screen.getByTestId('chat-thread-scroll')
    const metrics = mockScrollMetrics(thread, {
      clientHeight: 500,
      scrollHeight: 1_000,
      scrollTop: 410,
    })

    fireEvent.scroll(thread)
    metrics.set({ scrollHeight: 1_200 })
    rerender(
      <ChatThread
        messages={[
          message({
            content: 'Start of the streamed response. More response text.',
            status: 'streaming',
          }),
        ]}
        onCitationSelect={vi.fn()}
      />,
    )

    expect(metrics.scrollTop).toBe(1_200)
    expect(screen.queryByRole('button', { name: /jump to latest message/i })).not.toBeInTheDocument()
  })

  it('preserves scroll position when streaming grows after the user scrolls up', () => {
    const { rerender } = render(
      <ChatThread
        messages={[
          message({
            content: 'Start of the streamed response.',
            status: 'streaming',
          }),
        ]}
        onCitationSelect={vi.fn()}
      />,
    )
    const thread = screen.getByTestId('chat-thread-scroll')
    const metrics = mockScrollMetrics(thread, {
      clientHeight: 500,
      scrollHeight: 1_000,
      scrollTop: 250,
    })

    fireEvent.scroll(thread)
    metrics.set({ scrollHeight: 1_200 })
    rerender(
      <ChatThread
        messages={[
          message({
            content: 'Start of the streamed response. More response text.',
            status: 'streaming',
          }),
        ]}
        onCitationSelect={vi.fn()}
      />,
    )

    expect(metrics.scrollTop).toBe(250)
    expect(screen.getByRole('button', { name: /jump to latest message/i })).toBeInTheDocument()
  })

  it('resumes auto-scroll after the user scrolls back near the bottom', () => {
    const { rerender } = render(
      <ChatThread
        messages={[
          message({
            content: 'Start of the streamed response.',
            status: 'streaming',
          }),
        ]}
        onCitationSelect={vi.fn()}
      />,
    )
    const thread = screen.getByTestId('chat-thread-scroll')
    const metrics = mockScrollMetrics(thread, {
      clientHeight: 500,
      scrollHeight: 1_200,
      scrollTop: 250,
    })

    fireEvent.scroll(thread)
    expect(screen.getByRole('button', { name: /jump to latest message/i })).toBeInTheDocument()

    metrics.set({ scrollTop: 620 })
    fireEvent.scroll(thread)
    metrics.set({ scrollHeight: 1_350 })
    rerender(
      <ChatThread
        messages={[
          message({
            content: 'Start of the streamed response. More response text.',
            status: 'streaming',
          }),
        ]}
        onCitationSelect={vi.fn()}
      />,
    )

    expect(metrics.scrollTop).toBe(1_350)
    expect(screen.queryByRole('button', { name: /jump to latest message/i })).not.toBeInTheDocument()
  })

  it('jumps to the latest message when the floating latest control is clicked', () => {
    render(
      <ChatThread
        messages={[
          message({
            content: 'A previous response.',
            status: 'complete',
          }),
        ]}
        onCitationSelect={vi.fn()}
      />,
    )
    const thread = screen.getByTestId('chat-thread-scroll')
    const metrics = mockScrollMetrics(thread, {
      clientHeight: 500,
      scrollHeight: 1_100,
      scrollTop: 300,
    })

    fireEvent.scroll(thread)
    fireEvent.click(screen.getByRole('button', { name: /jump to latest message/i }))

    expect(metrics.scrollTop).toBe(1_100)
    expect(screen.queryByRole('button', { name: /jump to latest message/i })).not.toBeInTheDocument()
  })

  it('forces latest when a pending outgoing message appears', () => {
    const { rerender } = render(
      <ChatThread
        messages={[
          message({
            content: 'A previous response.',
            status: 'complete',
          }),
        ]}
        onCitationSelect={vi.fn()}
      />,
    )
    const thread = screen.getByTestId('chat-thread-scroll')
    const metrics = mockScrollMetrics(thread, {
      clientHeight: 500,
      scrollHeight: 1_100,
      scrollTop: 300,
    })

    fireEvent.scroll(thread)
    expect(screen.getByRole('button', { name: /jump to latest message/i })).toBeInTheDocument()

    metrics.set({ scrollHeight: 1_250 })
    rerender(
      <ChatThread
        messages={[
          message({
            content: 'A previous response.',
            status: 'complete',
          }),
        ]}
        onCitationSelect={vi.fn()}
        pendingMessage="Can I follow up?"
      />,
    )

    expect(metrics.scrollTop).toBe(1_250)
    expect(screen.getByText('Can I follow up?')).toBeInTheDocument()
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
