import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  createAdminChatMessageStream,
  createAdminChatSession,
  getAdminChatSession,
  listAdminChatSessions,
  submitAdminChatMessage,
} from '@/src/lib/api/endpoints/adminChat'
import { apiClient } from '@/src/lib/api/client'

vi.mock('@/src/lib/api/client', () => ({
  apiClient: vi.fn(),
}))

const session = {
  id: 'admin-chat-session-1',
  title: 'Weekly NIL questions',
  status: 'active',
  context_window_start: null,
  context_window_end: null,
  last_message_at: null,
  created_at: '2026-06-29T12:00:00Z',
  updated_at: '2026-06-29T12:00:00Z',
}

describe('admin chat endpoints', () => {
  const originalEventSource = global.EventSource

  beforeEach(() => {
    vi.mocked(apiClient).mockReset()
    global.EventSource = originalEventSource
  })

  it('lists admin chat sessions on the documented route', async () => {
    vi.mocked(apiClient).mockResolvedValueOnce([session])

    await listAdminChatSessions()

    expect(apiClient).toHaveBeenCalledWith('/api/v1/admin/chat/sessions')
  })

  it('creates admin chat sessions with optional context windows', async () => {
    vi.mocked(apiClient).mockResolvedValueOnce(session)

    await createAdminChatSession({
      title: 'Weekly NIL questions',
      context_window_start: '2026-06-01T00:00:00Z',
      context_window_end: '2026-06-08T00:00:00Z',
    })

    expect(apiClient).toHaveBeenCalledWith('/api/v1/admin/chat/sessions', {
      method: 'POST',
      json: {
        title: 'Weekly NIL questions',
        context_window_start: '2026-06-01T00:00:00Z',
        context_window_end: '2026-06-08T00:00:00Z',
      },
    })
  })

  it('loads one admin chat session with messages', async () => {
    vi.mocked(apiClient).mockResolvedValueOnce({ ...session, messages: [] })

    await getAdminChatSession('admin-chat-session-1')

    expect(apiClient).toHaveBeenCalledWith('/api/v1/admin/chat/sessions/admin-chat-session-1')
  })

  it('submits admin chat questions on the documented route', async () => {
    vi.mocked(apiClient).mockResolvedValueOnce({
      session_id: 'admin-chat-session-1',
      user_message_id: 'admin-user-message-1',
      assistant_message_id: 'admin-assistant-message-1',
      task_id: 'task-1',
      stream_url:
        '/api/v1/admin/chat/sessions/admin-chat-session-1/messages/admin-assistant-message-1/stream?task_id=task-1',
      status: 'streaming',
    })

    await submitAdminChatMessage({
      sessionId: 'admin-chat-session-1',
      question: 'What are athletes most confused about this week?',
      window: '7d',
    })

    expect(apiClient).toHaveBeenCalledWith(
      '/api/v1/admin/chat/sessions/admin-chat-session-1/messages',
      {
        method: 'POST',
        json: {
          question: 'What are athletes most confused about this week?',
          window: '7d',
        },
      },
    )
  })

  it('opens admin chat streams with backend cookies included', () => {
    const eventSource = vi.fn()
    vi.stubGlobal('EventSource', eventSource)

    createAdminChatMessageStream(
      '/api/v1/admin/chat/sessions/s1/messages/m1/stream?task_id=t1',
    )

    expect(eventSource).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/admin/chat/sessions/s1/messages/m1/stream?task_id=t1',
      { withCredentials: true },
    )
  })
})
