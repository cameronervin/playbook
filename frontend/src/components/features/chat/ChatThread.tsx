'use client'

import { AlertTriangle, FileText } from 'lucide-react'
import { ChatThreadSkeleton } from '@/src/components/features/loading/PlaybookLoaders'
import { PlaybookMark } from '@/src/components/ui'
import type { ChatMessage, Citation } from '@/src/types/conversations'

interface ChatThreadProps {
  isLoading?: boolean
  messages: ChatMessage[]
  onCitationSelect: (citation: Citation) => void
  pendingMessage?: string | null
}

export function ChatThread({
  isLoading = false,
  messages,
  onCitationSelect,
  pendingMessage = null,
}: ChatThreadProps) {
  if (isLoading) return <ChatThreadSkeleton />

  return (
    <div className="pb-chat-thread">
      <div className="pb-chat-content flex w-full flex-col gap-6 px-7">
        {messages.length === 0 && !pendingMessage ? (
          <EmptyState />
        ) : (
          <>
            {messages.map((message) =>
              message.role === 'user' ? (
                <UserMessage key={message.id} message={message} />
              ) : (
                <AssistantMessage key={message.id} message={message} onCitationSelect={onCitationSelect} />
              ),
            )}
            {pendingMessage && (
              <>
                <UserMessage message={createPendingMessage('pending-user-message', 'user', pendingMessage)} />
                <AssistantMessage
                  message={createPendingMessage('pending-assistant-message', 'assistant', '')}
                  onCitationSelect={onCitationSelect}
                />
              </>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center gap-3 pb-4 pt-[13vh] text-center">
      <div className="flex items-center justify-center gap-3.5">
        <PlaybookMark className="text-fg-1" size={36} />
        <h1 className="pb-chat-empty-title">
          Ask PlaybookAI
        </h1>
      </div>
      <p className="pb-chat-body m-0 text-balance text-fg-3">
        Get answers to your athletics questions,
        <br />
        PlaybookAI is your coach off the field.
      </p>
    </div>
  )
}

function UserMessage({ message }: { message: ChatMessage }) {
  return (
    <div className="flex justify-end">
      <div className="pb-chat-user-message">
        {message.content}
      </div>
    </div>
  )
}

interface AssistantMessageProps {
  message: ChatMessage
  onCitationSelect: (citation: Citation) => void
}

function AssistantMessage({ message, onCitationSelect }: AssistantMessageProps) {
  const isFailed = message.status === 'failed'
  const hasContent = message.content.trim().length > 0
  const isAwaitingContent = message.status === 'pending' || message.status === 'streaming'
  const isThinking = !isFailed && isAwaitingContent && !hasContent
  const checkedSources = getNumberMetadata(message.metadata, 'checked_sources')
  const responseTime = getStringMetadata(message.metadata, 'response_time')

  return (
    <article className="flex">
      <div className="min-w-0 flex-1">
        <p className="pb-ui-xs mb-2 text-fg-3">
          <span className="font-semibold text-fg-1">PlaybookAI</span>
        </p>
        {isFailed ? (
          <div className="pb-ui-sm flex items-center gap-2 rounded-md border border-danger/40 bg-danger-bg px-3 py-2 text-danger">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span>{getStringMetadata(message.metadata, 'stream_error') ?? 'Playbook could not finish that response.'}</span>
          </div>
        ) : isThinking ? (
          <div className="pb-ui-sm flex items-center gap-3 py-1 text-fg-3">
            <span className="animate-pb-pulse text-brand">
              <PlaybookMark size={22} />
            </span>
            <span className="pb-think">Thinking...</span>
          </div>
        ) : (
          <>
            <p className="pb-chat-body whitespace-pre-wrap">{message.content}</p>
            {message.citations.length > 0 && (
              <div className="mt-3.5 flex flex-wrap gap-2">
                {message.citations.map((citation) => (
                  <button
                    className="pb-focus-control pb-ui-xs inline-flex items-center gap-2 rounded-sm border border-border-strong bg-surface px-2.5 py-1.5 font-medium text-fg-2 transition hover:border-border-brand hover:text-fg-1"
                    key={citation.id}
                    onClick={() => onCitationSelect(citation)}
                    type="button"
                  >
                    <FileText className="h-3.5 w-3.5 text-brand" />
                    {citation.source_title}
                  </button>
                ))}
              </div>
            )}
            {(checkedSources || responseTime) && (
              <p className="pb-ui-xs mt-3 text-fg-3">
                {checkedSources ? `Checked ${checkedSources} sources` : 'Checked sources'}
                {responseTime ? ` · ${responseTime}` : null}
              </p>
            )}
          </>
        )}
      </div>
    </article>
  )
}

function createPendingMessage(id: string, role: 'user' | 'assistant', content: string): ChatMessage {
  return {
    id,
    conversation_id: 'pending-conversation',
    role,
    content,
    status: role === 'assistant' ? 'pending' : 'complete',
    safety_outcome: null,
    topic_labels: [],
    risk_labels: [],
    metadata: {},
    citations: [],
    created_at: new Date(0).toISOString(),
  }
}

function getNumberMetadata(metadata: Record<string, unknown>, key: string) {
  const value = metadata[key]
  return typeof value === 'number' ? value : null
}

function getStringMetadata(metadata: Record<string, unknown>, key: string) {
  const value = metadata[key]
  return typeof value === 'string' ? value : null
}
