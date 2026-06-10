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

export interface ConversationFileSummary {
  id: string
  conversation_id: string
  message_id: string | null
  filename: string
  content_type: string
  size_bytes: number
  extraction_status: string
  chunk_count: number
  created_at: string
  updated_at: string
}

export interface ConversationDetail extends ConversationSummary {
  messages: ChatMessage[]
  files: ConversationFileSummary[]
}

export interface ConversationCreateRequest {
  initial_message: string
}
