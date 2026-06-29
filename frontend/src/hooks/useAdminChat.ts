import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useRef } from 'react'
import {
  createAdminChatMessageStream,
  createAdminChatSession,
  getAdminChatSession,
  listAdminChatSessions,
  submitAdminChatMessage,
} from '@/src/lib/api/endpoints/adminChat'
import { QUERY_KEYS } from '@/src/lib/constants/config'
import type {
  AdminChatAnswerType,
  AdminChatMessage,
  AdminChatMessageSubmitResponse,
  AdminChatReference,
  AdminChatReferenceType,
  AdminChatSession,
  AdminChatSessionDetail,
} from '@/src/types/adminChat'

interface AdminChatStreamTarget {
  assistantMessageId: string
  sessionId: string
  streamUrl: string
}

interface AdminChatStreamPayload {
  stream_id: string
  task_id: string
  event_type: 'chunk' | 'progress' | 'complete' | 'error'
  created_at: string
  data: Record<string, unknown>
}

export const useAdminChatSessions = (enabled: boolean) =>
  useQuery({
    queryKey: [QUERY_KEYS.adminChatSessions],
    queryFn: listAdminChatSessions,
    enabled,
  })

export const useAdminChatSessionDetail = (
  sessionId: string | null,
  enabled = true,
) =>
  useQuery({
    queryKey: [QUERY_KEYS.adminChatSessionDetail, sessionId],
    queryFn: () => getAdminChatSession(sessionId ?? ''),
    enabled: enabled && Boolean(sessionId),
  })

export const useCreateAdminChatSession = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: createAdminChatSession,
    onSuccess: (session) => {
      queryClient.setQueryData<AdminChatSessionDetail>(
        [QUERY_KEYS.adminChatSessionDetail, session.id],
        (detail) => detail ?? { ...session, messages: [] },
      )
      upsertAdminChatSession(queryClient, session)
    },
  })
}

export const useSubmitAdminChatMessage = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: submitAdminChatMessage,
    onSuccess: async (response, variables) => {
      appendAdminChatMessages(
        queryClient,
        variables.sessionId,
        createSubmittedAdminChatMessages(variables.question, response),
      )
      touchAdminChatSession(queryClient, variables.sessionId)
      await markAdminChatSessionsStale(queryClient)
    },
  })
}

export const useAdminChatMessageStream = () => {
  const queryClient = useQueryClient()
  const streamRef = useRef<EventSource | null>(null)

  const stop = useCallback(() => {
    streamRef.current?.close()
    streamRef.current = null
  }, [])

  useEffect(() => stop, [stop])

  const reconcileSession = useCallback(
    (sessionId: string) =>
      Promise.all([
        queryClient.invalidateQueries({
          queryKey: [QUERY_KEYS.adminChatSessionDetail, sessionId],
        }),
        markAdminChatSessionsStale(queryClient),
      ]),
    [queryClient],
  )

  const start = useCallback(
    ({ assistantMessageId, sessionId, streamUrl }: AdminChatStreamTarget) => {
      stop()
      const stream = createAdminChatMessageStream(streamUrl)
      streamRef.current = stream

      stream.addEventListener('chunk', (event) => {
        const payload = parseStreamPayload(event)
        const content = getStringData(payload, 'content')
        if (!content) return
        updateAssistantMessage(queryClient, sessionId, assistantMessageId, (message) => ({
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
        updateAssistantMessage(queryClient, sessionId, assistantMessageId, (message) => ({
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
        const content = getStringData(payload, 'content') ?? getStringData(payload, 'answer')
        const references = getReferencesData(payload)
        const answerType = getAnswerTypeData(payload)
        updateAssistantMessage(queryClient, sessionId, assistantMessageId, (message) => ({
          ...message,
          answer_type: answerType ?? message.answer_type,
          content: content ?? message.content,
          metadata: {
            ...message.metadata,
            last_stream_id: payload?.stream_id,
          },
          references: references ?? message.references,
          status: 'complete',
        }))
        stop()
        void reconcileSession(sessionId)
      })

      stream.addEventListener('error', (event) => {
        const payload = parseStreamPayload(event)
        updateAssistantMessage(queryClient, sessionId, assistantMessageId, (message) => ({
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
        void reconcileSession(sessionId)
      })

      stream.onerror = () => {
        updateAssistantMessage(queryClient, sessionId, assistantMessageId, (message) => ({
          ...message,
          metadata: {
            ...message.metadata,
            stream_error: 'Playbook lost the analytics response stream.',
          },
          status: 'failed',
        }))
        stop()
        void reconcileSession(sessionId)
      }
    },
    [queryClient, reconcileSession, stop],
  )

  return { start, stop }
}

export function createSubmittedAdminChatMessages(
  content: string,
  response: AdminChatMessageSubmitResponse,
): AdminChatMessage[] {
  const now = new Date().toISOString()
  return [
    {
      id: response.user_message_id,
      session_id: response.session_id,
      role: 'user',
      content,
      status: 'complete',
      references: [],
      metadata: {},
      answer_type: null,
      created_at: now,
    },
    {
      id: response.assistant_message_id,
      session_id: response.session_id,
      role: 'assistant',
      content: '',
      status: response.status,
      references: [],
      metadata: {
        task_id: response.task_id,
        user_message_id: response.user_message_id,
      },
      answer_type: null,
      created_at: now,
    },
  ]
}

function upsertAdminChatSession(
  queryClient: QueryClient,
  session: AdminChatSession,
): void {
  queryClient.setQueryData<AdminChatSession[]>(
    [QUERY_KEYS.adminChatSessions],
    (sessions) => {
      if (!sessions) return [session]
      return [
        session,
        ...sessions.filter((existing) => existing.id !== session.id),
      ]
    },
  )
}

function touchAdminChatSession(queryClient: QueryClient, sessionId: string): void {
  const timestamp = new Date().toISOString()
  queryClient.setQueryData<AdminChatSession[]>(
    [QUERY_KEYS.adminChatSessions],
    (sessions) =>
      sessions?.map((session) =>
        session.id === sessionId
          ? {
              ...session,
              last_message_at: timestamp,
              updated_at: timestamp,
            }
          : session,
      ),
  )
  queryClient.setQueryData<AdminChatSessionDetail>(
    [QUERY_KEYS.adminChatSessionDetail, sessionId],
    (session) =>
      session
        ? {
            ...session,
            last_message_at: timestamp,
            updated_at: timestamp,
          }
        : session,
  )
}

function appendAdminChatMessages(
  queryClient: QueryClient,
  sessionId: string,
  messages: AdminChatMessage[],
): void {
  queryClient.setQueryData<AdminChatSessionDetail>(
    [QUERY_KEYS.adminChatSessionDetail, sessionId],
    (session) => {
      if (!session) return session
      return {
        ...session,
        messages: [...session.messages, ...messages],
      }
    },
  )
}

function updateAssistantMessage(
  queryClient: QueryClient,
  sessionId: string,
  assistantMessageId: string,
  update: (message: AdminChatMessage) => AdminChatMessage,
): void {
  queryClient.setQueryData<AdminChatSessionDetail>(
    [QUERY_KEYS.adminChatSessionDetail, sessionId],
    (session) => {
      if (!session) return session
      return {
        ...session,
        messages: session.messages.map((message) =>
          message.id === assistantMessageId ? update(message) : message,
        ),
      }
    },
  )
}

function markAdminChatSessionsStale(queryClient: QueryClient): Promise<void> {
  return queryClient.invalidateQueries({
    queryKey: [QUERY_KEYS.adminChatSessions],
    refetchType: 'none',
  })
}

function parseStreamPayload(event: Event): AdminChatStreamPayload | null {
  if (!(event instanceof MessageEvent) || typeof event.data !== 'string') return null
  try {
    return JSON.parse(event.data) as AdminChatStreamPayload
  } catch {
    return null
  }
}

function getStringData(payload: AdminChatStreamPayload | null, key: string): string | null {
  const value = payload?.data[key]
  return typeof value === 'string' ? value : null
}

function getReferencesData(payload: AdminChatStreamPayload | null): AdminChatReference[] | null {
  const value = payload?.data.references
  if (!Array.isArray(value)) return null
  const references = value.filter(isAdminChatReference)
  return references.length > 0 ? references : null
}

function getAnswerTypeData(payload: AdminChatStreamPayload | null): AdminChatAnswerType | null {
  const value = payload?.data.answer_type
  if (value === 'analytics_answer' || value === 'refusal' || value === 'unsupported') {
    return value
  }
  return null
}

function isAdminChatReference(value: unknown): value is AdminChatReference {
  if (!value || typeof value !== 'object') return false
  const reference = value as Record<string, unknown>
  return isAdminChatReferenceType(reference.type) && typeof reference.id === 'string'
}

function isAdminChatReferenceType(value: unknown): value is AdminChatReferenceType {
  return value === 'metric' || value === 'dashboard_insight' || value === 'query'
}
