'use client'

import * as DropdownMenuPrimitive from '@radix-ui/react-dropdown-menu'
import type { ReactNode } from 'react'
import { AlertTriangle, FileText, LoaderCircle, MoreHorizontal, Pencil, RefreshCw, Trash2 } from 'lucide-react'
import { cn } from '@/src/lib/utils/cn'
import type { KBDocument } from '@/src/types/kb'

interface AdminKBDocumentRowProps {
  canManage: boolean
  document: KBDocument
  onDelete: () => void
  onEdit: () => void
  onRetry: () => void
}

export function AdminKBDocumentRow({
  canManage,
  document,
  onDelete,
  onEdit,
  onRetry,
}: AdminKBDocumentRowProps) {
  const failed = document.processing_status === 'failed'
  const pendingUpload = document.processing_status === 'upload_pending'
  const queued = document.processing_status === 'uploaded'
  const processing = document.processing_status === 'processing'
  const extension = getDocumentExtension(document)
  const tags = getDocumentTags(document).slice(0, 2)

  return (
    <article className="pb-admin-kb-doc-row" data-failed={failed}>
      <div className="pb-admin-kb-doc-main">
        <span className="pb-admin-kb-file-icon" aria-hidden="true">
          <FileText size={17} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="pb-admin-kb-doc-title">{document.title}</span>
          </div>
          <p className="pb-admin-kb-doc-meta">{formatDocumentMeta(document)}</p>
        </div>
        {tags.length > 0 && (
          <div className="hidden shrink-0 items-center gap-1.5 md:flex">
            {tags.map((tag) => (
              <span className="pb-admin-kb-chip" key={tag}>
                {tag}
              </span>
            ))}
          </div>
        )}
        {pendingUpload && (
          <span className="pb-admin-kb-status text-warning">
            <LoaderCircle className="pb-spin" size={14} />
            Pending upload
          </span>
        )}
        {queued && (
          <span className="pb-admin-kb-status text-info">
            <LoaderCircle className="pb-spin" size={14} />
            Queued
          </span>
        )}
        {processing && (
          <span className="pb-admin-kb-status text-info">
            <LoaderCircle className="pb-spin" size={14} />
            Processing
          </span>
        )}
        {failed && (
          <span className="pb-admin-kb-status text-danger">
            <AlertTriangle size={14} />
            Failed
          </span>
        )}
        {!pendingUpload && !queued && !processing && !failed && <span className="pb-admin-kb-ext">{extension}</span>}
        <DocumentActions
          canManage={canManage}
          documentTitle={document.title}
          failed={failed}
          onDelete={onDelete}
          onEdit={onEdit}
          onRetry={onRetry}
        />
      </div>
      {failed && document.failure_reason && (
        <div className="pb-admin-kb-failure">
          <AlertTriangle className="shrink-0 text-danger" size={14} />
          <span className="flex-1">{document.failure_reason}</span>
          {canManage && (
            <button className="pb-admin-kb-inline-action" onClick={onRetry} type="button" aria-label={`Retry ${document.title}`}>
              <RefreshCw size={13} />
              Retry
            </button>
          )}
        </div>
      )}
    </article>
  )
}

interface DocumentActionsProps {
  canManage: boolean
  documentTitle: string
  failed: boolean
  onDelete: () => void
  onEdit: () => void
  onRetry: () => void
}

function DocumentActions({
  canManage,
  documentTitle,
  failed,
  onDelete,
  onEdit,
  onRetry,
}: DocumentActionsProps) {
  return (
    <DropdownMenuPrimitive.Root>
      <DropdownMenuPrimitive.Trigger asChild>
        <button className="pb-admin-kb-icon-button" type="button" aria-label={`Actions for ${documentTitle}`}>
          <MoreHorizontal size={18} />
        </button>
      </DropdownMenuPrimitive.Trigger>
      <DropdownMenuPrimitive.Portal>
        <DropdownMenuPrimitive.Content align="end" className="pb-admin-menu" sideOffset={4}>
          <DropdownMenuItem icon={<Pencil size={16} />} onSelect={onEdit}>
            Edit metadata
          </DropdownMenuItem>
          {failed && canManage && (
            <DropdownMenuItem icon={<RefreshCw size={16} />} onSelect={onRetry}>
              Retry processing
            </DropdownMenuItem>
          )}
          {canManage && (
            <DropdownMenuItem danger icon={<Trash2 size={16} />} onSelect={onDelete}>
              Delete / archive
            </DropdownMenuItem>
          )}
        </DropdownMenuPrimitive.Content>
      </DropdownMenuPrimitive.Portal>
    </DropdownMenuPrimitive.Root>
  )
}

interface DropdownMenuItemProps {
  children: ReactNode
  danger?: boolean
  icon: ReactNode
  onSelect: () => void
}

function DropdownMenuItem({ children, danger = false, icon, onSelect }: DropdownMenuItemProps) {
  return (
    <DropdownMenuPrimitive.Item
      className={cn('pb-admin-menu-item pb-focus-item', danger && 'text-danger focus:bg-danger-bg focus:text-danger')}
      onSelect={onSelect}
    >
      <span className={cn('text-fg-3', danger && 'text-danger')}>{icon}</span>
      {children}
    </DropdownMenuPrimitive.Item>
  )
}

function getDocumentTags(document: KBDocument): string[] {
  const topics = readStringList(document.metadata_tags.topics)
  const tags = readStringList(document.metadata_tags.tags)
  const topic = readString(document.metadata_tags.topic)
  return [...topics, ...tags, ...(topic ? [topic] : [])]
}

function getDocumentExtension(document: KBDocument): string {
  const name = document.filename || document.title
  return name.split('.').pop()?.toLowerCase() || 'doc'
}

function formatDocumentMeta(document: KBDocument): string {
  const parts = [formatBytes(document.size_bytes), formatDate(document.created_at), 'Playbook admin']
  return parts.filter(Boolean).join(' · ')
}

function formatBytes(sizeBytes: number): string {
  if (!Number.isFinite(sizeBytes) || sizeBytes <= 0) return 'Unknown size'
  if (sizeBytes >= 1_000_000) return `${(sizeBytes / 1_000_000).toFixed(1)} MB`
  return `${Math.max(1, Math.round(sizeBytes / 1_000))} KB`
}

function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Uploaded recently'
  return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric' }).format(date)
}

function readString(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null
}

function readStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
}
