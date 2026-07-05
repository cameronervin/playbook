import { afterEach, describe, expect, it, vi } from 'vitest'
import { collectUniqueCitations, groupConversations } from '@/src/components/features/chat/conversationGrouping'
import type { Citation, ConversationSummary } from '@/src/types/conversations'

function summary(id: string, title: string, createdAt: string, lastMessageAt: string | null = createdAt): ConversationSummary {
  return {
    id,
    organization_id: 'org-1',
    athlete_id: 'user-1',
    title,
    status: 'active',
    last_message_at: lastMessageAt,
    created_at: createdAt,
    updated_at: createdAt,
  }
}

function citation(id: string, sourceTitle: string): Citation {
  return {
    id,
    message_id: 'message-1',
    document_id: 'doc-1',
    chunk_id: 'chunk-1',
    source_title: sourceTitle,
    source_metadata: {},
    rank: 1,
    created_at: '2026-06-18T12:00:00.000Z',
  }
}

describe('conversationGrouping', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('sorts conversations newest first and groups by current day buckets', () => {
    vi.setSystemTime(new Date('2026-06-18T16:00:00.000Z'))

    const groups = groupConversations([
      summary('previous', 'Previous topic', '2026-06-14T15:00:00.000Z'),
      summary('today-old', 'Earlier today', '2026-06-18T10:00:00.000Z'),
      summary('yesterday', 'Yesterday topic', '2026-06-17T20:00:00.000Z'),
      summary('today-new', 'Later today', '2026-06-18T15:00:00.000Z'),
    ])

    expect(groups.map((group) => group.label)).toEqual(['Today', 'Yesterday', 'Previous 7 days'])
    expect(groups[0].conversations.map((conversation) => conversation.id)).toEqual(['today-new', 'today-old'])
    expect(groups[1].conversations.map((conversation) => conversation.id)).toEqual(['yesterday'])
    expect(groups[2].conversations.map((conversation) => conversation.id)).toEqual(['previous'])
  })

  it('falls back to created_at when last_message_at is null', () => {
    vi.setSystemTime(new Date('2026-06-18T16:00:00.000Z'))

    const groups = groupConversations([
      summary('old-created', 'Old created', '2026-06-15T15:00:00.000Z', null),
      summary('today-created', 'Today created', '2026-06-18T09:00:00.000Z', null),
    ])

    expect(groups.map((group) => group.label)).toEqual(['Today', 'Previous 7 days'])
    expect(groups[0].conversations[0].id).toBe('today-created')
  })

  it('deduplicates citations by id and falls back to source title', () => {
    const citations = collectUniqueCitations([
      citation('citation-1', 'NIL handbook'),
      citation('citation-1', 'NIL handbook duplicate'),
      citation('', 'Travel policy'),
      citation('', 'Travel policy'),
    ])

    expect(citations.map((item) => item.source_title)).toEqual(['NIL handbook', 'Travel policy'])
  })
})
