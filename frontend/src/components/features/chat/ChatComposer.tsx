'use client'

import { forwardRef, useImperativeHandle, useRef, useState, type ChangeEvent } from 'react'
import { AlertTriangle, FileText, LoaderCircle, Paperclip, Send } from 'lucide-react'
import { Button } from '@/src/components/ui'
import { SUPPORTED_UPLOAD_ACCEPT } from '@/src/lib/constants/uploads'
import type { ConversationFileSummary } from '@/src/types/conversations'
import type { ChatUploadRow } from '@/src/components/features/chat/chatTypes'

export interface ChatComposerHandle {
  focus: () => void
}

interface ChatComposerProps {
  canAttach?: boolean
  conversationFiles?: ConversationFileSummary[]
  disabled?: boolean
  localUploads?: ChatUploadRow[]
  onAttachFile?: (file: File) => void
  onSend: (message: string) => void
}

export const ChatComposer = forwardRef<ChatComposerHandle, ChatComposerProps>(function ChatComposer(
  {
    canAttach = false,
    conversationFiles = [],
    disabled = false,
    localUploads = [],
    onAttachFile,
    onSend,
  },
  ref,
) {
  const [draft, setDraft] = useState('')
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)
  const canSend = Boolean(draft.trim()) && !disabled
  const attachTitle = canAttach ? 'Attach a conversation file' : 'File upload is unavailable right now'

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

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) onAttachFile?.(file)
    event.target.value = ''
  }

  return (
    <div className="pb-chat-composer">
      <div className="pb-chat-content w-full">
        {(localUploads.length > 0 || conversationFiles.length > 0) && (
          <div className="mb-2.5 flex flex-col gap-1.5">
            {localUploads.map((upload) => (
              <ChatUploadStatus key={upload.id} upload={upload} />
            ))}
            {conversationFiles.map((file) => (
              <ConversationFileStatus file={file} key={file.id} />
            ))}
          </div>
        )}
        <div
          className="pb-chat-composer-shell pb-field-shell"
        >
          <textarea
            aria-label="Message Playbook"
            className="pb-chat-composer-input px-1 pb-2.5 pt-1"
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
            <input
              accept={SUPPORTED_UPLOAD_ACCEPT}
              aria-label="Attach conversation file"
              className="sr-only"
              disabled={!canAttach || disabled}
              onChange={handleFileChange}
              ref={fileInputRef}
              type="file"
            />
            <button
              aria-label="Attach file"
              className="pb-focus-control inline-flex h-9 w-9 items-center justify-center rounded-sm border border-transparent text-fg-2 transition hover:bg-surface-hover hover:text-fg-1 disabled:cursor-not-allowed disabled:text-fg-4"
              disabled={!canAttach || disabled}
              onClick={() => fileInputRef.current?.click()}
              title={attachTitle}
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
        <p className="pb-ui-xs mt-2.5 text-center text-fg-4">
          Responses are AI generated. Review to confirm accuracy.
        </p>
      </div>
    </div>
  )
})

function ChatUploadStatus({ upload }: { upload: ChatUploadRow }) {
  const failed = upload.phase === 'failed'
  return (
    <div className="rounded-md border border-border bg-surface px-3 py-2">
      <div className="flex items-center gap-2">
        <FileText className="h-4 w-4 shrink-0 text-fg-3" />
        <span className="pb-chat-meta min-w-0 flex-1 truncate font-medium text-fg-1">{upload.file.name}</span>
        <span className={failed ? 'pb-ui-xs flex items-center gap-1 text-danger' : 'pb-ui-xs flex items-center gap-1 text-info'} role="status">
          {failed ? <AlertTriangle className="h-3.5 w-3.5" /> : <LoaderCircle className="pb-spin h-3.5 w-3.5" />}
          {formatChatUploadPhase(upload)}
        </span>
      </div>
      {upload.phase === 'uploading' && (
        <div className="mt-2 h-1.5 overflow-hidden rounded-pill bg-surface-hover" aria-hidden="true">
          <span className="block h-full rounded-pill bg-brand" style={{ width: `${upload.percent}%` }} />
        </div>
      )}
      {failed && upload.errorMessage && (
        <p className="pb-ui-xs mt-1 text-danger">{upload.errorMessage}</p>
      )}
    </div>
  )
}

function ConversationFileStatus({ file }: { file: ConversationFileSummary }) {
  const failed = file.extraction_status === 'failed'
  return (
    <div className="rounded-md border border-border bg-surface px-3 py-2">
      <div className="flex items-center gap-2">
        <FileText className="h-4 w-4 shrink-0 text-fg-3" />
        <span className="pb-chat-meta min-w-0 flex-1 truncate font-medium text-fg-1">{file.filename}</span>
        <span className={failed ? 'pb-ui-xs flex items-center gap-1 text-danger' : 'pb-ui-xs flex items-center gap-1 text-info'} role="status">
          {failed ? <AlertTriangle className="h-3.5 w-3.5" /> : <LoaderCircle className="pb-spin h-3.5 w-3.5" />}
          {formatConversationFileStatus(file)}
        </span>
      </div>
    </div>
  )
}

function formatChatUploadPhase(upload: ChatUploadRow): string {
  if (upload.phase === 'pending') return 'Pending upload'
  if (upload.phase === 'requesting') return 'Preparing'
  if (upload.phase === 'uploading') return `Uploading ${upload.percent}%`
  if (upload.phase === 'queued') return 'Queued'
  return 'Failed'
}

function formatConversationFileStatus(file: ConversationFileSummary): string {
  if (file.extraction_status === 'upload_pending') return 'Pending upload'
  if (file.extraction_status === 'uploaded') return 'Queued'
  if (file.extraction_status === 'extracting') return 'Extracting'
  if (file.extraction_status === 'ready') return file.chunk_count > 0 ? `Ready · ${file.chunk_count} chunks` : 'Ready'
  return 'Failed'
}
