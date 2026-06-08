'use client'

import { forwardRef, useImperativeHandle, useRef, useState } from 'react'
import { Paperclip, Send } from 'lucide-react'
import { Button } from '@/src/components/ui'

export interface ChatComposerHandle {
  focus: () => void
}

interface ChatComposerProps {
  disabled?: boolean
  onSend: (message: string) => void
}

export const ChatComposer = forwardRef<ChatComposerHandle, ChatComposerProps>(function ChatComposer(
  { disabled = false, onSend },
  ref,
) {
  const [draft, setDraft] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)
  const canSend = Boolean(draft.trim()) && !disabled

  useImperativeHandle(ref, () => ({
    focus: () => textareaRef.current?.focus(),
  }))

  const resizeTextarea = (textarea: HTMLTextAreaElement) => {
    textarea.style.height = 'auto'
    textarea.style.height = `${Math.min(textarea.scrollHeight, 160)}px`
  }

  const submit = () => {
    const message = draft.trim()
    if (!message || disabled) return
    onSend(message)
    setDraft('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  return (
    <div className="flex shrink-0 justify-center bg-bg-base px-7 pb-[22px] pt-3.5">
      <div className="w-full max-w-[760px]">
        <div
          className="pb-field-shell rounded-lg border border-border-solid bg-surface p-3 shadow-sm transition"
        >
          <textarea
            aria-label="Message Playbook"
            className="min-h-[48px] w-full resize-none border-0 bg-transparent px-1 pb-2.5 pt-1 text-[15px] leading-6 text-fg-1 outline-none placeholder:text-fg-4"
            disabled={disabled}
            onChange={(event) => {
              setDraft(event.target.value)
              resizeTextarea(event.target)
            }}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                submit()
              }
            }}
            placeholder="Ask Playbook a question..."
            ref={textareaRef}
            rows={1}
            value={draft}
          />
          <div className="flex items-center gap-2.5">
            <button
              aria-label="Attach file"
              className="inline-flex h-9 w-9 items-center justify-center rounded-sm text-fg-2 transition hover:bg-surface-hover hover:text-fg-1 disabled:cursor-not-allowed disabled:text-fg-4"
              disabled
              title="Conversation file upload is planned for the next backend phase"
              type="button"
            >
              <Paperclip className="h-[18px] w-[18px]" />
            </button>
            <Button
              className="ml-auto px-4"
              disabled={!canSend}
              onClick={submit}
              size="sm"
              type="button"
            >
              Ask
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </div>
        <p className="mt-2.5 text-center text-[11px] text-fg-4">
          Responses are AI generated. Review to confirm accuracy.
        </p>
      </div>
    </div>
  )
})
