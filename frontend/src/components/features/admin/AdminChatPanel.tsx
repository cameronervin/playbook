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
    <WorkspaceSidePanel aria-label="Analytics AI Agent" className="w-[384px] animate-pb-panel">
      <header className="flex h-[60px] shrink-0 items-center gap-3 border-b border-border px-4">
        <AgentAvatar className="h-8 w-8">
          <Zap className="h-4 w-4" />
        </AgentAvatar>
        <div className="min-w-0">
          <h2 className="font-display text-[14.5px] font-bold text-fg-1">Analytics AI Agent</h2>
        </div>
        <button
          aria-label="Close analytics chat"
          className="ml-auto inline-flex h-[34px] w-[34px] items-center justify-center rounded-sm text-fg-2 transition hover:bg-surface-hover hover:text-fg-1"
          onClick={onClose}
          type="button"
        >
          <X className="h-[18px] w-[18px]" />
        </button>
      </header>
      <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-4">
        {messages.length === 0 ? (
          <div className="mt-1">
            <p className="mb-[18px] text-[13.5px] leading-relaxed text-fg-2">
              Ask an AI agent about query patterns, support gaps, risk trends, and more.
            </p>
            <p className="mb-2.5 px-0.5 text-[11.5px] font-bold uppercase tracking-[0.06em] text-fg-3">Try asking</p>
            <div className="grid gap-2">
              {ADMIN_CHAT_SUGGESTIONS.map((suggestion) => (
                <button
                  className="flex items-center gap-2.5 rounded-md border border-border-strong bg-surface px-3 py-2.5 text-left text-[13px] text-fg-1 transition hover:border-border-brand hover:bg-surface-raised"
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
            className="max-h-28 min-h-[34px] flex-1 resize-none border-0 bg-transparent py-1 text-[13.5px] leading-normal text-fg-1 outline-none placeholder:text-fg-4"
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
            className="flex h-[34px] w-[34px] shrink-0 items-center justify-center rounded-md bg-brand text-fg-on-brand transition hover:bg-brand-hover disabled:cursor-not-allowed disabled:bg-surface-hover disabled:text-fg-4"
            disabled={!draft.trim()}
            type="submit"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
        <p className="mt-2 text-center text-[11px] text-fg-4">Responses are AI generated. Review to confirm accuracy.</p>
      </form>
    </WorkspaceSidePanel>
  )
}

function AdminChatMessage({ message }: { message: AdminChatMessageFixture }) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <p className="max-w-[86%] rounded-[12px_12px_3px_12px] border border-border-brand bg-brand-soft px-3.5 py-2.5 text-[13.5px] leading-normal text-fg-1">
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
        <p className={cn('m-0 text-[13.5px] leading-relaxed', message.answer_type === 'declined' ? 'text-fg-3' : 'text-fg-2')}>
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
          className="inline-flex items-center gap-1.5 rounded-pill border border-border bg-surface px-2 py-1 text-[11px] font-semibold text-fg-2"
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
