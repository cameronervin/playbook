import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  completeConversationFileUpload,
  createConversation,
  createConversationFileUploadIntent,
  createConversationMessageStream,
  submitConversationMessage,
  uploadConversationFile,
} from '@/src/lib/api/endpoints/conversations'
import { apiClient } from '@/src/lib/api/client'
import { postDirectUpload } from '@/src/lib/api/directUpload'
import type {
  ConversationFileSummary,
  ConversationFileUploadIntentResponse,
} from '@/src/types/conversations'

vi.mock('@/src/lib/api/client', () => ({
  apiClient: vi.fn(),
}))

vi.mock('@/src/lib/api/directUpload', () => ({
  postDirectUpload: vi.fn(),
}))

const fileSummary: ConversationFileSummary = {
  id: 'file-1',
  conversation_id: 'conversation-1',
  message_id: null,
  filename: 'contract.pdf',
  content_type: 'application/pdf',
  size_bytes: 12,
  extraction_status: 'upload_pending',
  chunk_count: 0,
  created_at: '2026-06-17T12:00:00Z',
  updated_at: '2026-06-17T12:00:00Z',
}

const intent: ConversationFileUploadIntentResponse = {
  file: fileSummary,
  upload: {
    upload_request_id: 'upload-request-1',
    method: 'POST',
    url: 'https://storage.example/upload',
    fields: { key: 'private/key.pdf' },
    expires_at: '2026-06-17T12:15:00Z',
  },
}

describe('conversation file upload endpoints', () => {
  const originalEventSource = global.EventSource

  beforeEach(() => {
    vi.mocked(apiClient).mockReset()
    vi.mocked(postDirectUpload).mockReset()
    global.EventSource = originalEventSource
  })

  it('starts a conversation on the documented first-send route', async () => {
    vi.mocked(apiClient).mockResolvedValueOnce({
      assistant_message_id: 'assistant-1',
      conversation: { id: 'conversation-1', messages: [] },
      status: 'streaming',
      stream_url: '/api/v1/conversations/conversation-1/messages/assistant-1/stream?task_id=task-1',
      task_id: 'task-1',
      user_message_id: 'user-message-1',
    })

    await createConversation({ content: 'Can I travel?' })

    expect(apiClient).toHaveBeenCalledWith('/api/v1/conversations', {
      method: 'POST',
      json: { content: 'Can I travel?' },
    })
  })

  it('submits follow-up messages on the documented route', async () => {
    vi.mocked(apiClient).mockResolvedValueOnce({
      assistant_message_id: 'assistant-1',
      status: 'streaming',
      stream_url: '/api/v1/conversations/conversation-1/messages/assistant-1/stream?task_id=task-1',
      task_id: 'task-1',
      user_message_id: 'user-message-1',
    })

    await submitConversationMessage({
      conversationId: 'conversation-1',
      content: 'What about tomorrow?',
      file_ids: ['file-1'],
    })

    expect(apiClient).toHaveBeenCalledWith('/api/v1/conversations/conversation-1/messages', {
      method: 'POST',
      json: {
        content: 'What about tomorrow?',
        file_ids: ['file-1'],
      },
    })
  })

  it('opens conversation streams with backend cookies included', () => {
    const eventSource = vi.fn()
    vi.stubGlobal('EventSource', eventSource)

    createConversationMessageStream('/api/v1/conversations/c1/messages/m1/stream?task_id=t1')

    expect(eventSource).toHaveBeenCalledWith(
      'http://localhost:8000/api/v1/conversations/c1/messages/m1/stream?task_id=t1',
      { withCredentials: true },
    )
  })

  it('creates a conversation file upload intent on the documented route', async () => {
    vi.mocked(apiClient).mockResolvedValueOnce(intent)

    await createConversationFileUploadIntent('conversation-1', {
      filename: 'contract.pdf',
      content_type: 'application/pdf',
      size_bytes: 12,
      message_id: null,
    })

    expect(apiClient).toHaveBeenCalledWith('/api/v1/conversations/conversation-1/files', {
      method: 'POST',
      json: {
        filename: 'contract.pdf',
        content_type: 'application/pdf',
        size_bytes: 12,
        message_id: null,
      },
    })
  })

  it('completes a conversation file upload on the documented route', async () => {
    vi.mocked(apiClient).mockResolvedValueOnce({ ...fileSummary, extraction_status: 'uploaded' })

    await completeConversationFileUpload('conversation-1', 'file-1', 'upload-request-1')

    expect(apiClient).toHaveBeenCalledWith('/api/v1/conversations/conversation-1/files/file-1/upload-complete', {
      method: 'POST',
      json: { upload_request_id: 'upload-request-1' },
    })
  })

  it('performs intent, storage POST, then completion for the high-level upload', async () => {
    const file = new File(['hello world'], 'contract.pdf', { type: 'application/pdf' })
    vi.mocked(apiClient)
      .mockResolvedValueOnce(intent)
      .mockResolvedValueOnce({ ...fileSummary, extraction_status: 'uploaded' })

    await uploadConversationFile({ conversationId: 'conversation-1', file })

    expect(postDirectUpload).toHaveBeenCalledWith(expect.objectContaining({ contract: intent.upload, file }))
    expect(apiClient).toHaveBeenNthCalledWith(
      2,
      '/api/v1/conversations/conversation-1/files/file-1/upload-complete',
      {
        method: 'POST',
        json: { upload_request_id: 'upload-request-1' },
      },
    )
  })
})
