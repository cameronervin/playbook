import type { ConversationSummary } from '@/src/types/conversations'

export interface ConversationGroup {
  label: 'Today' | 'Yesterday' | 'Previous 7 days'
  conversations: ConversationSummary[]
}
