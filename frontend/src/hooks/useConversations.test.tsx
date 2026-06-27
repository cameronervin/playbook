import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useConversationMessageStream } from '@/src/hooks/useConversations'
import { createConversationMessageStream } from '@/src/lib/api/endpoints/conversations'
import { QUERY_KEYS } from '@/src/lib/constants/config'
import type { ConversationDetail, ConversationSummary } from '@/src/types/conversations'

const streamMocks = vi.hoisted(() => ({
  stream: null as FakeEventSource | null,
}))

vi.mock('@/src/lib/api/endpoints/conversations', () => ({
  createConversation: vi.fn(),
  createConversationMessageStream: vi.fn(() => streamMocks.stream),
  getConversation: vi.fn(),
  listConversations: vi.fn(),
  submitConversationMessage: vi.fn(),
  uploadConversationFile: vi.fn(),
}))

class FakeEventSource {
  listeners = new Map<string, (event: Event) => void>()
  onerror: ((event: Event) => void) | null = null
  closed = false

  addEventListener(type: string, listener: (event: Event) => void): void {
    this.listeners.set(type, listener)
  }

  close(): void {
    this.closed = true
  }

  emit(type: string, data: object): void {
    this.listeners.get(type)?.(
      new MessageEvent(type, { data: JSON.stringify(data) }),
    )
  }
}

function summary(title: string | null): ConversationSummary {
  return {
    id: 'conversation-1',
    organization_id: 'org-1',
    athlete_id: 'athlete-1',
    title,
    status: 'active',
    last_message_at: '2026-06-19T12:00:00Z',
    created_at: '2026-06-19T12:00:00Z',
    updated_at: '2026-06-19T12:00:00Z',
  }
}

function detail(title: string | null): ConversationDetail {
  return {
    ...summary(title),
    messages: [
      {
        id: 'assistant-1',
        conversation_id: 'conversation-1',
        role: 'assistant',
        content: 'Disclose the NIL deal first.',
        status: 'streaming',
        safety_outcome: null,
        topic_labels: [],
        risk_labels: [],
        metadata: {},
        citations: [],
        created_at: '2026-06-19T12:00:00Z',
      },
    ],
    files: [],
  }
}

function renderStreamHook(queryClient: QueryClient) {
  return renderHook(() => useConversationMessageStream(), {
    wrapper: ({ children }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    ),
  })
}

describe('useConversationMessageStream', () => {
  beforeEach(() => {
    streamMocks.stream = new FakeEventSource()
    vi.mocked(createConversationMessageStream).mockClear()
  })

  it('updates conversation title caches from the terminal complete event', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    queryClient.setQueryData([QUERY_KEYS.conversations], [
      summary('Can I accept this NIL deal'),
    ])
    queryClient.setQueryData(
      [QUERY_KEYS.conversationDetail, 'conversation-1'],
      detail('Can I accept this NIL deal'),
    )
    const { result } = renderStreamHook(queryClient)

    act(() => {
      result.current.start({
        assistantMessageId: 'assistant-1',
        conversationId: 'conversation-1',
        streamUrl: '/api/v1/conversations/conversation-1/messages/assistant-1/stream?task_id=task-1',
      })
    })
    act(() => {
      streamMocks.stream?.emit('complete', {
        stream_id: '2-0',
        task_id: 'task-1',
        event_type: 'complete',
        created_at: '2026-06-19T12:00:01Z',
        data: { conversation_title: 'NIL Deal Disclosure' },
      })
    })

    await waitFor(() => {
      expect(
        queryClient.getQueryData<ConversationDetail>([
          QUERY_KEYS.conversationDetail,
          'conversation-1',
        ])?.title,
      ).toBe('NIL Deal Disclosure')
    })
    expect(
      queryClient.getQueryData<ConversationSummary[]>([
        QUERY_KEYS.conversations,
      ])?.[0]?.title,
    ).toBe('NIL Deal Disclosure')
    expect(streamMocks.stream?.closed).toBe(true)
  })
})
