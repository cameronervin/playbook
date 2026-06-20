'use client'

import { FormEvent, useState } from 'react'
import { CornerDownRight, FileText, Send, X, Zap } from 'lucide-react'
import { WorkspaceSidePanel } from '@/src/components/features/workspace/WorkspaceShell'
import { AgentAvatar } from '@/src/components/ui'
import { ADMIN_CHAT_SUGGESTIONS } from '@/src/lib/fixtures/admin'
import { cn } from '@/src/lib/utils/cn'
import type { AdminChatMessageFixture, AdminChatReferenceFixture } from '@/src/types/fixtures'

interface AdminChatPanelProps {
  messages: AdminChatMessageFixture[]
  onClose: () => void
  onSend: (content: string) => void
}

export function AdminChatPanel({ messages, onClose, onSend }: AdminChatPanelProps) {
  const [draft, setDraft] = useState('')

  const submit = (content: string) => {
    const value = content.trim()
    if (!value) return
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
        <AgentAvatar className="h-8 w-8">
          <Zap className="h-4 w-4" />
        </AgentAvatar>
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
      <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-4">
        {messages.length === 0 ? (
          <div className="mt-1">
            <p className="pb-admin-chat-copy mb-[18px]">
              Ask an AI agent about query patterns, support gaps, risk trends, and more.
            </p>
            <p className="pb-dashboard-section-label mb-2.5 px-0.5">Try asking</p>
            <div className="grid gap-2">
              {ADMIN_CHAT_SUGGESTIONS.map((suggestion) => (
                <button
                  className="pb-admin-chat-suggestion pb-focus-control"
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
          messages.map((message) => <AdminChatMessage key={message.id} message={message} />)
        )}
      </div>
      <form className="shrink-0 border-t border-border p-4" onSubmit={handleSubmit}>
        <div className="flex items-end gap-2 rounded-lg border border-border-strong bg-surface py-2 pl-3 pr-2">
          <textarea
            className="pb-admin-chat-input py-1"
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                submit(draft)
              }
            }}
            placeholder="Ask about the analytics..."
            rows={1}
            value={draft}
          />
          <button
            aria-label="Send analytics question"
            className="pb-focus-control flex h-[34px] w-[34px] shrink-0 items-center justify-center rounded-md border border-transparent bg-brand text-fg-on-brand transition hover:bg-brand-hover disabled:cursor-not-allowed disabled:bg-surface-hover disabled:text-fg-4"
            disabled={!draft.trim()}
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

function AdminChatMessage({ message }: { message: AdminChatMessageFixture }) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <p className="pb-admin-chat-user-message">
          {message.content}
        </p>
      </div>
    )
  }

  return (
    <div className="flex gap-3">
      <AgentAvatar className="h-[30px] w-[30px]">
        <Zap className="h-[15px] w-[15px]" />
      </AgentAvatar>
      <div className="min-w-0 flex-1">
        <p className={cn('pb-admin-chat-copy m-0', message.answer_type === 'declined' ? 'text-fg-3' : 'text-fg-2')}>
          {message.content}
        </p>
        {message.refs && message.refs.length > 0 && <SourcesDisclosure refs={message.refs} />}
      </div>
    </div>
  )
}

function SourcesDisclosure({ refs }: { refs: AdminChatReferenceFixture[] }) {
  return (
    <div className="mt-2.5 flex flex-wrap gap-1.5">
      {refs.map((ref) => (
        <span
          className="pb-dashboard-meta inline-flex items-center gap-1.5 rounded-pill border border-border bg-surface px-2 py-1 font-semibold text-fg-2"
          key={`${ref.type}-${ref.id}`}
        >
          {ref.type === 'dashboard_insight' ? <Zap className="h-3 w-3 text-brand" /> : <FileText className="h-3 w-3 text-brand" />}
          <span className="text-fg-3">{formatReferenceType(ref.type)}</span>
          <span>{ref.id}</span>
        </span>
      ))}
    </div>
  )
}

function formatReferenceType(type: AdminChatReferenceFixture['type']) {
  if (type === 'dashboard_insight') return 'Insight'
  if (type === 'metric') return 'Metric'
  return 'Query'
}
