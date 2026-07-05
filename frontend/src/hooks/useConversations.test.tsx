import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  useConversationMessageStream,
  useCreateConversation,
  useSubmitConversationMessage,
} from '@/src/hooks/useConversations'
import {
  createConversation,
  createConversationMessageStream,
  submitConversationMessage,
} from '@/src/lib/api/endpoints/conversations'
import { QUERY_KEYS } from '@/src/lib/constants/config'
import type {
  ConversationDetail,
  ConversationStartResponse,
  ConversationSummary,
  MessageSubmitResponse,
} from '@/src/types/conversations'

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

function renderCreateConversationHook(queryClient: QueryClient) {
  return renderHook(() => useCreateConversation(), {
    wrapper: ({ children }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    ),
  })
}

function renderSubmitConversationMessageHook(queryClient: QueryClient) {
  return renderHook(() => useSubmitConversationMessage(), {
    wrapper: ({ children }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    ),
  })
}

describe('conversation hooks', () => {
  beforeEach(() => {
    streamMocks.stream = new FakeEventSource()
    vi.mocked(createConversationMessageStream).mockClear()
    vi.mocked(createConversation).mockReset()
    vi.mocked(submitConversationMessage).mockReset()
  })

  it('upserts a first-send conversation into the list cache without active refetch', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    const invalidateQueries = vi.spyOn(queryClient, 'invalidateQueries')
    const existing = summary('Existing NIL question')
    const createdConversation = detail('Travel form review')
    createdConversation.id = 'conversation-new'
    createdConversation.last_message_at = '2026-06-19T12:05:00Z'
    createdConversation.updated_at = '2026-06-19T12:05:00Z'
    queryClient.setQueryData([QUERY_KEYS.conversations], [existing])
    vi.mocked(createConversation).mockResolvedValueOnce({
      assistant_message_id: 'assistant-new',
      conversation: createdConversation,
      status: 'streaming',
      stream_url: '/api/v1/conversations/conversation-new/messages/assistant-new/stream?task_id=task-new',
      task_id: 'task-new',
      user_message_id: 'user-new',
    } satisfies ConversationStartResponse)
    const { result } = renderCreateConversationHook(queryClient)

    await act(async () => {
      await result.current.mutateAsync({ content: 'Can you review this travel form?' })
    })

    expect(
      queryClient.getQueryData<ConversationSummary[]>([QUERY_KEYS.conversations]),
    ).toEqual([
      expect.objectContaining({ id: 'conversation-new', title: 'Travel form review' }),
      existing,
    ])
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: [QUERY_KEYS.conversations],
      refetchType: 'none',
    })
    expect(invalidateQueries).not.toHaveBeenCalledWith({
      queryKey: [QUERY_KEYS.conversations],
    })
  })

  it('updates a follow-up conversation summary without active list refetch', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    const invalidateQueries = vi.spyOn(queryClient, 'invalidateQueries')
    queryClient.setQueryData([QUERY_KEYS.conversations], [
      summary('NIL Deal Disclosure'),
    ])
    vi.mocked(submitConversationMessage).mockResolvedValueOnce({
      assistant_message_id: 'assistant-follow-up',
      status: 'streaming',
      stream_url: '/api/v1/conversations/conversation-1/messages/assistant-follow-up/stream?task_id=task-follow-up',
      task_id: 'task-follow-up',
      user_message_id: 'user-follow-up',
    } satisfies MessageSubmitResponse)
    const { result } = renderSubmitConversationMessageHook(queryClient)

    await act(async () => {
      await result.current.mutateAsync({
        conversationId: 'conversation-1',
        content: 'Can I follow up?',
      })
    })

    const cached = queryClient.getQueryData<ConversationSummary[]>([
      QUERY_KEYS.conversations,
    ])
    expect(cached?.[0]).toEqual(
      expect.objectContaining({
        id: 'conversation-1',
        title: 'NIL Deal Disclosure',
      }),
    )
    expect(cached?.[0]?.last_message_at).not.toBe('2026-06-19T12:00:00Z')
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: [QUERY_KEYS.conversations],
      refetchType: 'none',
    })
    expect(invalidateQueries).not.toHaveBeenCalledWith({
      queryKey: [QUERY_KEYS.conversations],
    })
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

  it('marks stream completion stale without actively refetching the conversation list', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    const invalidateQueries = vi.spyOn(queryClient, 'invalidateQueries')
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
        stream_id: '3-0',
        task_id: 'task-1',
        event_type: 'complete',
        created_at: '2026-06-19T12:00:03Z',
        data: {},
      })
    })

    await waitFor(() => {
      expect(
        queryClient.getQueryData<ConversationDetail>([
          QUERY_KEYS.conversationDetail,
          'conversation-1',
        ])?.messages[0]?.status,
      ).toBe('complete')
    })
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: [QUERY_KEYS.conversationDetail, 'conversation-1'],
    })
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: [QUERY_KEYS.conversations],
      refetchType: 'none',
    })
    expect(invalidateQueries).not.toHaveBeenCalledWith({
      queryKey: [QUERY_KEYS.conversations],
    })
  })

  it('appends streamed chunks in order and does not duplicate on complete', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
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
      streamMocks.stream?.emit('chunk', {
        stream_id: '1-0',
        task_id: 'task-1',
        event_type: 'chunk',
        created_at: '2026-06-19T12:00:01Z',
        data: { content: ' Disclose' },
      })
      streamMocks.stream?.emit('chunk', {
        stream_id: '2-0',
        task_id: 'task-1',
        event_type: 'chunk',
        created_at: '2026-06-19T12:00:02Z',
        data: { content: ' before signing.' },
      })
      streamMocks.stream?.emit('complete', {
        stream_id: '3-0',
        task_id: 'task-1',
        event_type: 'complete',
        created_at: '2026-06-19T12:00:03Z',
        data: {},
      })
    })

    await waitFor(() => {
      expect(
        queryClient.getQueryData<ConversationDetail>([
          QUERY_KEYS.conversationDetail,
          'conversation-1',
        ])?.messages[0]?.content,
      ).toBe('Disclose the NIL deal first. Disclose before signing.')
    })
    expect(
      queryClient.getQueryData<ConversationDetail>([
        QUERY_KEYS.conversationDetail,
        'conversation-1',
      ])?.messages[0]?.status,
    ).toBe('complete')
    expect(streamMocks.stream?.closed).toBe(true)
  })
})
