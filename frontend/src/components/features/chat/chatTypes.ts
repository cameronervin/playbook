import type { ConversationSummary } from '@/src/types/conversations'

export interface ConversationGroup {
  label: 'Today' | 'Yesterday' | 'Previous 7 days'
  conversations: ConversationSummary[]
}

export type ChatUploadPhase = 'pending' | 'requesting' | 'uploading' | 'queued' | 'failed'

export interface ChatUploadRow {
  errorMessage?: string
  file: File
  id: string
  percent: number
  phase: ChatUploadPhase
}
