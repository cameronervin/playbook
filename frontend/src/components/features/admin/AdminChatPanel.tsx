'use client'

import { FormEvent, useMemo, useState } from 'react'
import { AlertTriangle, BotMessageSquare, CornerDownRight, Send, X } from 'lucide-react'
import { WorkspaceSidePanel } from '@/src/components/features/workspace/WorkspaceShell'
import { useStreamingThreadScroll } from '@/src/components/features/workspace/useStreamingThreadScroll'
import { AgentAvatar } from '@/src/components/ui'
import { ADMIN_CHAT_SUGGESTIONS } from '@/src/lib/fixtures/admin'
import { cn } from '@/src/lib/utils/cn'
import type { AdminChatMessage } from '@/src/types/adminChat'

interface AdminChatPanelProps {
  isBusy?: boolean
  isError?: boolean
  isLoading?: boolean
  messages: AdminChatMessage[]
  onClose: () => void
  onSend: (content: string) => void
  pendingMessage?: string | null
}

export function AdminChatPanel({
  isBusy = false,
  isError = false,
  isLoading = false,
  messages,
  onClose,
  onSend,
  pendingMessage = null,
}: AdminChatPanelProps) {
  const [draft, setDraft] = useState('')
  const scrollSignal = useMemo(
    () => createAdminChatScrollSignal(messages, pendingMessage),
    [messages, pendingMessage],
  )
  const {
    handleScroll,
    threadRef,
  } = useStreamingThreadScroll({
    forceFollowSignal: pendingMessage,
    resetKey: messages[0]?.session_id ?? null,
    scrollSignal,
  })
  const hasThreadContent = messages.length > 0 || pendingMessage !== null

  const submit = (content: string) => {
    const value = content.trim()
    if (!value || isBusy) return
    onSend(value)
    setDraft('')
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    submit(draft)
  }

  return (
    <WorkspaceSidePanel aria-label="Analytics AI Agent" className="pb-workspace-side-panel-wide animate-pb-panel">
      <header className="pb-panel-header px-4">
        <div className="min-w-0">
          <h2 className="pb-panel-title">Analytics AI Agent</h2>
        </div>
        <button
          aria-label="Close analytics chat"
          className="pb-panel-close pb-focus-control ml-auto"
          onClick={onClose}
          type="button"
        >
          <X className="h-[18px] w-[18px]" />
        </button>
      </header>
      <div
        className="relative flex flex-1 flex-col gap-4 overflow-y-auto p-4"
        data-testid="admin-chat-thread-scroll"
        onScroll={handleScroll}
        ref={threadRef}
      >
        {isLoading ? (
          <p className="pb-admin-chat-copy mt-1 text-fg-3">Loading analytics chat...</p>
        ) : !hasThreadContent ? (
          <div className="mt-1">
            <p className="pb-admin-chat-copy mb-[18px]">
              Ask an AI agent about query patterns, support gaps, risk trends, and more.
            </p>
            <p className="pb-dashboard-section-label mb-2.5 px-0.5">Try asking</p>
            <div className="grid gap-2">
              {ADMIN_CHAT_SUGGESTIONS.map((suggestion) => (
                <button
                  className="pb-admin-chat-suggestion pb-focus-control"
                  disabled={isBusy}
                  key={suggestion}
                  onClick={() => submit(suggestion)}
                  type="button"
                >
                  <CornerDownRight className="h-[15px] w-[15px] shrink-0 text-brand" />
                  <span className="flex-1">{suggestion}</span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {messages.map((message) => <AdminChatMessage key={message.id} message={message} />)}
            {pendingMessage && (
              <>
                <AdminChatMessage message={createPendingAdminMessage('pending-admin-user-message', 'user', pendingMessage)} />
                <AdminChatMessage message={createPendingAdminMessage('pending-admin-assistant-message', 'assistant', '')} />
              </>
            )}
          </>
        )}
        {isError && (
          <p className="pb-dashboard-meta rounded-md border border-danger/30 bg-danger-bg px-3 py-2 text-danger">
            Analytics chat could not complete that request. Try again.
          </p>
        )}
      </div>
      <form className="shrink-0 border-t border-border p-4" onSubmit={handleSubmit}>
        <div className="pb-chat-composer-shell pb-field-shell pb-admin-chat-composer-shell">
          <textarea
            aria-label="Message Analytics AI"
            className="pb-chat-composer-input pb-admin-chat-input py-1"
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                submit(draft)
              }
            }}
            placeholder="Ask the Analytics AI a question..."
            rows={1}
            value={draft}
          />
          <button
            aria-label="Send analytics question"
            className="pb-focus-control flex h-[34px] w-[34px] shrink-0 items-center justify-center rounded-md border border-transparent bg-brand text-fg-on-brand transition hover:bg-brand-hover disabled:cursor-not-allowed disabled:bg-surface-hover disabled:text-fg-4"
            disabled={isBusy || !draft.trim()}
            type="submit"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
        <p className="pb-dashboard-meta mt-2 text-center text-fg-4">Responses are AI generated. Review to confirm accuracy.</p>
      </form>
    </WorkspaceSidePanel>
  )
}

function AdminChatMessage({ message }: { message: AdminChatMessage }) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <p className="pb-chat-user-message pb-admin-chat-user-message">
          {message.content}
        </p>
      </div>
    )
  }

  const failed = message.status === 'failed'
  const declined = message.answer_type === 'refusal' || message.answer_type === 'unsupported'
  const content = message.content || getStreamError(message.metadata) || (failed ? 'The analytics response failed. Try again.' : '')
  const hasContent = content.trim().length > 0
  const isThinking = !failed && message.status === 'streaming' && !hasContent

  return (
    <div className="flex gap-3">
      <AgentAvatar className="h-[30px] w-[30px]">
        <BotMessageSquare className="h-[15px] w-[15px]" />
      </AgentAvatar>
      <div className="min-w-0 flex-1">
        {isThinking ? (
          <div className="pb-ui-sm flex items-center py-1 text-fg-3">
            <span className="pb-thinking-shimmer">Thinking...</span>
          </div>
        ) : failed ? (
          <div className="pb-ui-sm flex items-center gap-2 rounded-md border border-danger/40 bg-danger-bg px-3 py-2 text-danger">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span>{content}</span>
          </div>
        ) : (
          <>
            <p
              className={cn(
                'pb-chat-body m-0 whitespace-pre-wrap',
                message.status === 'streaming' && 'pb-streaming',
                declined ? 'text-fg-3' : 'text-fg-2',
              )}
            >
              {content}
            </p>
          </>
        )}
      </div>
    </div>
  )
}

function getStreamError(metadata: Record<string, unknown>): string | null {
  const error = metadata.stream_error
  return typeof error === 'string' ? error : null
}

function createPendingAdminMessage(
  id: string,
  role: AdminChatMessage['role'],
  content: string,
): AdminChatMessage {
  return {
    id,
    session_id: 'pending-admin-chat-session',
    role,
    content,
    status: role === 'assistant' ? 'streaming' : 'complete',
    references: [],
    metadata: {},
    answer_type: null,
    created_at: new Date(0).toISOString(),
  }
}

function createAdminChatScrollSignal(
  messages: AdminChatMessage[],
  pendingMessage: string | null,
): string {
  return [
    pendingMessage ?? '',
    ...messages.map((message) => [
      message.id,
      message.status,
      message.content.length,
    ].join(':')),
  ].join('|')
}
