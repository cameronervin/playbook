import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef } from 'react'
import {
  createConversation,
  createConversationMessageStream,
  getConversation,
  listConversations,
  submitConversationMessage,
  uploadConversationFile,
} from '@/src/lib/api/endpoints/conversations'
import { QUERY_KEYS } from '@/src/lib/constants/config'
import type {
  ChatMessage,
  ConversationDetail,
  ConversationSummary,
  MessageSubmitResponse,
} from '@/src/types/conversations'

const CONVERSATION_FILE_STATUS_REFETCH_INTERVAL_MS = 3_000

export const useConversations = () =>
  useQuery({
    queryKey: [QUERY_KEYS.conversations],
    queryFn: listConversations,
  })

export const useConversationDetail = (conversationId: string | null) =>
  useQuery({
    queryKey: [QUERY_KEYS.conversationDetail, conversationId],
    queryFn: () => getConversation(conversationId ?? ''),
    enabled: Boolean(conversationId),
    refetchInterval: (query) => {
      const conversation = query.state.data as ConversationDetail | undefined
      return hasActiveConversationFileStatus(conversation)
        ? CONVERSATION_FILE_STATUS_REFETCH_INTERVAL_MS
        : false
    },
  })

export const useCreateConversation = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: createConversation,
    onSuccess: async (data) => {
      queryClient.setQueryData(
        [QUERY_KEYS.conversationDetail, data.conversation.id],
        data.conversation,
      )
      upsertConversationSummary(queryClient, data.conversation)
      await markConversationListStale(queryClient)
    },
  })
}

export const useSubmitConversationMessage = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: submitConversationMessage,
    onSuccess: async (_data, variables) => {
      touchConversationSummary(queryClient, variables.conversationId)
      await markConversationListStale(queryClient)
    },
  })
}

export const useUploadConversationFile = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: uploadConversationFile,
    onSettled: async (_data, _error, variables) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.conversations] }),
        queryClient.invalidateQueries({
          queryKey: [QUERY_KEYS.conversationDetail, variables.conversationId],
        }),
      ])
    },
  })
}

function hasActiveConversationFileStatus(conversation: ConversationDetail | undefined): boolean {
  return Boolean(
    conversation?.files.some((file) =>
      ['upload_pending', 'uploaded', 'extracting'].includes(file.extraction_status),
    ),
  )
}

interface ConversationMessageStreamTarget {
  assistantMessageId: string
  conversationId: string
  streamUrl: string
}

interface AgentStreamPayload {
  stream_id: string
  task_id: string
  event_type: 'chunk' | 'progress' | 'complete' | 'error'
  created_at: string
  data: Record<string, unknown>
}

export const useConversationMessageStream = () => {
  const queryClient = useQueryClient()
  const streamRef = useRef<EventSource | null>(null)

  const stop = useCallback(() => {
    streamRef.current?.close()
    streamRef.current = null
  }, [])

  useEffect(() => stop, [stop])

  const reconcileConversation = useCallback(
    (conversationId: string) =>
      Promise.all([
        queryClient.invalidateQueries({
          queryKey: [QUERY_KEYS.conversationDetail, conversationId],
        }),
        markConversationListStale(queryClient),
      ]),
    [queryClient],
  )

  const start = useCallback(
    ({ assistantMessageId, conversationId, streamUrl }: ConversationMessageStreamTarget) => {
      stop()
      const stream = createConversationMessageStream(streamUrl)
      streamRef.current = stream

      stream.addEventListener('chunk', (event) => {
        const payload = parseStreamPayload(event)
        const content = getStringData(payload, 'content')
        if (!content) return
        updateAssistantMessage(queryClient, conversationId, assistantMessageId, (message) => ({
          ...message,
          content: `${message.content}${content}`,
          metadata: {
            ...message.metadata,
            last_stream_id: payload?.stream_id,
          },
          status: 'streaming',
        }))
      })

      stream.addEventListener('progress', (event) => {
        const payload = parseStreamPayload(event)
        const status = getStringData(payload, 'status')
        if (!status) return
        updateAssistantMessage(queryClient, conversationId, assistantMessageId, (message) => ({
          ...message,
          metadata: {
            ...message.metadata,
            stream_status: status,
            last_stream_id: payload?.stream_id,
          },
        }))
      })

      stream.addEventListener('complete', (event) => {
        const payload = parseStreamPayload(event)
        const conversationTitle = getStringData(payload, 'conversation_title')
        if (conversationTitle) {
          updateConversationTitle(queryClient, conversationId, conversationTitle)
        }
        updateAssistantMessage(queryClient, conversationId, assistantMessageId, (message) => ({
          ...message,
          metadata: {
            ...message.metadata,
            last_stream_id: payload?.stream_id,
          },
          status: 'complete',
        }))
        stop()
        void reconcileConversation(conversationId)
      })

      stream.addEventListener('error', (event) => {
        const payload = parseStreamPayload(event)
        updateAssistantMessage(queryClient, conversationId, assistantMessageId, (message) => ({
          ...message,
          metadata: {
            ...message.metadata,
            stream_error: getStringData(payload, 'message') ?? 'Stream failed.',
            stream_error_code: getStringData(payload, 'code'),
            last_stream_id: payload?.stream_id,
          },
          status: 'failed',
        }))
        stop()
        void reconcileConversation(conversationId)
      })

      stream.onerror = () => {
        updateAssistantMessage(queryClient, conversationId, assistantMessageId, (message) => ({
          ...message,
          metadata: {
            ...message.metadata,
            stream_error: 'Playbook lost the response stream.',
          },
          status: 'failed',
        }))
        stop()
        void reconcileConversation(conversationId)
      }
    },
    [reconcileConversation, queryClient, stop],
  )

  return { start, stop }
}

function upsertConversationSummary(
  queryClient: QueryClient,
  conversation: ConversationSummary,
): void {
  queryClient.setQueryData<ConversationSummary[]>(
    [QUERY_KEYS.conversations],
    (conversations) => {
      if (!conversations) return [conversation]
      return [
        conversation,
        ...conversations.filter((existing) => existing.id !== conversation.id),
      ]
    },
  )
}

function touchConversationSummary(
  queryClient: QueryClient,
  conversationId: string,
): void {
  const timestamp = new Date().toISOString()
  queryClient.setQueryData<ConversationSummary[]>(
    [QUERY_KEYS.conversations],
    (conversations) =>
      conversations?.map((conversation) =>
        conversation.id === conversationId
          ? {
              ...conversation,
              last_message_at: timestamp,
              updated_at: timestamp,
            }
          : conversation,
      ),
  )
}

function markConversationListStale(queryClient: QueryClient): Promise<void> {
  return queryClient.invalidateQueries({
    queryKey: [QUERY_KEYS.conversations],
    refetchType: 'none',
  })
}

export function createSubmittedMessages(
  conversationId: string,
  content: string,
  response: MessageSubmitResponse,
): ChatMessage[] {
  const now = new Date().toISOString()
  return [
    {
      id: response.user_message_id,
      conversation_id: conversationId,
      role: 'user',
      content,
      status: 'complete',
      safety_outcome: null,
      topic_labels: [],
      risk_labels: [],
      metadata: {},
      citations: [],
      created_at: now,
    },
    {
      id: response.assistant_message_id,
      conversation_id: conversationId,
      role: 'assistant',
      content: '',
      status: response.status,
      safety_outcome: null,
      topic_labels: [],
      risk_labels: [],
      metadata: {
        task_id: response.task_id,
        user_message_id: response.user_message_id,
      },
      citations: [],
      created_at: now,
    },
  ]
}

function updateConversationTitle(
  queryClient: QueryClient,
  conversationId: string,
  title: string,
): void {
  queryClient.setQueryData<ConversationDetail>(
    [QUERY_KEYS.conversationDetail, conversationId],
    (conversation) => (conversation ? { ...conversation, title } : conversation),
  )
  queryClient.setQueryData<ConversationSummary[]>(
    [QUERY_KEYS.conversations],
    (conversations) =>
      conversations?.map((conversation) =>
        conversation.id === conversationId ? { ...conversation, title } : conversation,
      ),
  )
}

function updateAssistantMessage(
  queryClient: QueryClient,
  conversationId: string,
  assistantMessageId: string,
  update: (message: ChatMessage) => ChatMessage,
): void {
  queryClient.setQueryData<ConversationDetail>(
    [QUERY_KEYS.conversationDetail, conversationId],
    (conversation) => {
      if (!conversation) return conversation
      return {
        ...conversation,
        messages: conversation.messages.map((message) =>
          message.id === assistantMessageId ? update(message) : message,
        ),
      }
    },
  )
}

function parseStreamPayload(event: Event): AgentStreamPayload | null {
  if (!(event instanceof MessageEvent) || typeof event.data !== 'string') return null
  try {
    return JSON.parse(event.data) as AgentStreamPayload
  } catch {
    return null
  }
}

function getStringData(payload: AgentStreamPayload | null, key: string): string | null {
  const value = payload?.data[key]
  return typeof value === 'string' ? value : null
}
