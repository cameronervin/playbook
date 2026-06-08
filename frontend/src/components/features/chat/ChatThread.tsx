'use client'

import { FileText } from 'lucide-react'
import { PlaybookMark } from '@/src/components/ui'
import type { ChatMessage, Citation } from '@/src/types/conversations'

interface ChatThreadProps {
  messages: ChatMessage[]
  onCitationSelect: (citation: Citation) => void
}

export function ChatThread({ messages, onCitationSelect }: ChatThreadProps) {
  return (
    <div className="flex min-h-0 flex-1 justify-center overflow-y-auto py-7">
      <div className="flex w-full max-w-[760px] flex-col gap-6 px-7">
        {messages.length === 0 ? (
          <EmptyState />
        ) : (
          messages.map((message) =>
            message.role === 'user' ? (
              <UserMessage key={message.id} message={message} />
            ) : (
              <AssistantMessage key={message.id} message={message} onCitationSelect={onCitationSelect} />
            ),
          )
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
        <h1 className="m-0 font-display text-[30px] font-extrabold leading-none tracking-normal text-fg-1 sm:text-[34px]">
          Ask PlaybookAI
        </h1>
      </div>
      <p className="m-0 text-balance text-[15px] leading-[1.55] text-fg-3">
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
      <div className="max-w-[78%] rounded-lg rounded-tr-sm border border-border bg-surface-hover px-4 py-3 text-[14.5px] leading-[1.55] text-fg-1">
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
  const isThinking = message.status === 'pending' || message.status === 'streaming' || !message.content
  const checkedSources = getNumberMetadata(message.metadata, 'checked_sources')
  const responseTime = getStringMetadata(message.metadata, 'response_time')

  return (
    <article className="flex">
      <div className="min-w-0 flex-1">
        <p className="mb-2 text-[12.5px] text-fg-3">
          <span className="font-semibold text-fg-1">PlaybookAI</span>
        </p>
        {isThinking ? (
          <div className="flex items-center gap-3 py-1 text-[13.5px] text-fg-3">
            <span className="animate-pb-pulse text-brand">
              <PlaybookMark size={22} />
            </span>
            <span>Thinking...</span>
          </div>
        ) : (
          <>
            <p className="whitespace-pre-wrap text-[14.5px] leading-[1.62] text-fg-1">{message.content}</p>
            {message.citations.length > 0 && (
              <div className="mt-3.5 flex flex-wrap gap-2">
                {message.citations.map((citation) => (
                  <button
                    className="inline-flex items-center gap-2 rounded-sm border border-border-strong bg-surface px-2.5 py-1.5 text-[10.5px] font-medium text-fg-2 transition hover:border-border-brand hover:text-fg-1"
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
              <p className="mt-3 text-[11px] text-fg-3">
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

function getNumberMetadata(metadata: Record<string, unknown>, key: string) {
  const value = metadata[key]
  return typeof value === 'number' ? value : null
}

function getStringMetadata(metadata: Record<string, unknown>, key: string) {
  const value = metadata[key]
  return typeof value === 'string' ? value : null
}
