import type { DirectUploadContract, DirectUploadMutationOptions } from '@/src/types/uploads'

export interface Citation {
  id: string
  message_id: string
  document_id: string | null
  chunk_id: string | null
  source_title: string
  source_metadata: Record<string, unknown>
  rank: number
  created_at: string
}

export interface ChatMessage {
  id: string
  conversation_id: string
  role: 'user' | 'assistant' | string
  content: string
  status: string
  safety_outcome: string | null
  topic_labels: unknown[]
  risk_labels: unknown[]
  metadata: Record<string, unknown>
  citations: Citation[]
  created_at: string
}

export interface ConversationSummary {
  id: string
  organization_id: string
  athlete_id: string
  title: string | null
  status: string
  last_message_at: string | null
  created_at: string
  updated_at: string
}

export type ConversationFileExtractionStatus = 'upload_pending' | 'uploaded' | 'extracting' | 'ready' | 'failed'

export interface ConversationFileSummary {
  id: string
  conversation_id: string
  message_id: string | null
  filename: string
  content_type: string
  size_bytes: number
  extraction_status: ConversationFileExtractionStatus
  chunk_count: number
  created_at: string
  updated_at: string
}

export interface ConversationDetail extends ConversationSummary {
  messages: ChatMessage[]
  files: ConversationFileSummary[]
}

export interface ConversationCreateRequest {
  content: string
}

export interface MessageSubmitRequest {
  conversationId: string
  content: string
  file_ids?: string[]
}

export interface MessageSubmitResponse {
  user_message_id: string
  assistant_message_id: string
  task_id: string
  stream_url: string
  status: string
}

export interface ConversationStartResponse extends MessageSubmitResponse {
  conversation: ConversationDetail
}

export interface ConversationFileUploadIntentRequest {
  filename: string
  content_type: string
  size_bytes: number
  message_id?: string | null
}

export interface ConversationFileUploadIntentResponse {
  file: ConversationFileSummary
  upload: DirectUploadContract
}

export interface UploadConversationFileRequest extends DirectUploadMutationOptions {
  conversationId: string
  file: File
  message_id?: string | null
}
