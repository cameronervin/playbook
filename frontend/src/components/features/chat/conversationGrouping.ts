import type { Citation, ConversationSummary } from '@/src/types/conversations'
import type { ConversationGroup } from '@/src/components/features/chat/chatTypes'

const CONVERSATION_GROUP_LABELS: ConversationGroup['label'][] = ['Today', 'Yesterday', 'Previous 7 days']
const DAY_MS = 86_400_000

export function groupConversations(conversations: ConversationSummary[]): ConversationGroup[] {
  const grouped: Record<ConversationGroup['label'], ConversationSummary[]> = {
    Today: [],
    Yesterday: [],
    'Previous 7 days': [],
  }

  conversations
    .slice()
    .sort((left, right) => getConversationTimestamp(right) - getConversationTimestamp(left))
    .forEach((conversation) => {
      grouped[getConversationGroupLabel(conversation)].push(conversation)
    })

  return CONVERSATION_GROUP_LABELS
    .map((label) => ({ label, conversations: grouped[label] }))
    .filter((group) => group.conversations.length > 0)
}

export function collectUniqueCitations(citations: Citation[]): Citation[] {
  const seen = new Set<string>()
  return citations.filter((citation) => {
    const key = citation.id || citation.source_title
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

function getConversationGroupLabel(conversation: ConversationSummary): ConversationGroup['label'] {
  const now = startOfDay(new Date())
  const timestamp = new Date(getConversationTimestamp(conversation))
  const conversationDay = startOfDay(timestamp)
  const daysAgo = Math.floor((now.getTime() - conversationDay.getTime()) / DAY_MS)

  if (daysAgo <= 0) return 'Today'
  if (daysAgo === 1) return 'Yesterday'
  return 'Previous 7 days'
}

function getConversationTimestamp(conversation: ConversationSummary): number {
  return new Date(conversation.last_message_at ?? conversation.created_at).getTime()
}

function startOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate())
}
