export type AdminChatAnswerType = 'analytics_answer' | 'refusal' | 'unsupported'

export type AdminChatMessageRole = 'user' | 'assistant'

export type AdminChatMessageStatus = 'complete' | 'streaming' | 'failed'

export type AdminChatReferenceType = 'metric' | 'dashboard_insight' | 'query'

export type AdminChatSessionStatus = 'active' | 'archived'

export type AdminChatWindow = `${number}d`

export interface AdminChatReference {
  type: AdminChatReferenceType
  id: string
}

export interface AdminChatSession {
  id: string
  title: string | null
  status: AdminChatSessionStatus
  context_window_start: string | null
  context_window_end: string | null
  last_message_at: string | null
  created_at: string
  updated_at: string
}

export interface AdminChatMessage {
  id: string
  session_id: string
  role: AdminChatMessageRole
  content: string
  status: AdminChatMessageStatus
  references: AdminChatReference[]
  metadata: Record<string, unknown>
  answer_type: AdminChatAnswerType | null
  created_at: string
}

export interface AdminChatSessionDetail extends AdminChatSession {
  messages: AdminChatMessage[]
}

export interface AdminChatSessionCreateRequest {
  title?: string | null
  context_window_start?: string | null
  context_window_end?: string | null
}

export interface AdminChatMessageSubmitPayload {
  question: string
  window?: AdminChatWindow
  window_start?: string | null
  window_end?: string | null
}

export interface AdminChatMessageSubmitRequest extends AdminChatMessageSubmitPayload {
  sessionId: string
}

export interface AdminChatMessageSubmitResponse {
  session_id: string
  user_message_id: string
  assistant_message_id: string
  task_id: string
  stream_url: string
  status: AdminChatMessageStatus
}
