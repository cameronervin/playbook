import { render, screen } from '@testing-library/react'
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
})
