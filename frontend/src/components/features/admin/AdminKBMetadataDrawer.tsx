'use client'

import * as DialogPrimitive from '@radix-ui/react-dialog'
import { FileText, Pencil, Trash2, X } from 'lucide-react'
import { useState } from 'react'
import { Button } from '@/src/components/ui'
import type { KBDocument, KBDocumentMetadataUpdateRequest } from '@/src/types/kb'

interface AdminKBMetadataDrawerProps {
  canManage: boolean
  document: KBDocument | null
  onClose: () => void
  onDelete: (documentId: string) => void
  onSave: (documentId: string, metadata: KBDocumentMetadataUpdateRequest) => void
}

export function AdminKBMetadataDrawer({ canManage, document, onClose, onDelete, onSave }: AdminKBMetadataDrawerProps) {
  if (!document) return null
  return <AdminKBMetadataDrawerForm canManage={canManage} document={document} onClose={onClose} onDelete={onDelete} onSave={onSave} />
}

interface AdminKBMetadataDrawerFormProps {
  canManage: boolean
  document: KBDocument
  onClose: () => void
  onDelete: (documentId: string) => void
  onSave: (documentId: string, metadata: KBDocumentMetadataUpdateRequest) => void
}

function AdminKBMetadataDrawerForm({
  canManage,
  document,
  onClose,
  onDelete,
  onSave,
}: AdminKBMetadataDrawerFormProps) {
  const [tags, setTags] = useState(getTags(document).join(', '))
  const [sourceDate, setSourceDate] = useState(document.source_date ?? '')

  const handleSave = () => {
    const nextTags = tags
      .split(',')
      .map((tag) => tag.trim())
      .filter(Boolean)
    onSave(document.id, {
      metadata_tags: {
        ...document.metadata_tags,
        topics: nextTags,
      },
      source_date: sourceDate || null,
    })
    onClose()
  }

  return (
    <DialogPrimitive.Root open onOpenChange={(open) => !open && onClose()}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="pb-admin-kb-drawer-overlay animate-pb-fade" />
        <DialogPrimitive.Content className="pb-admin-kb-drawer animate-pb-panel">
          <div className="pb-admin-kb-drawer-header">
            <Pencil className="text-brand" size={17} />
            <DialogPrimitive.Title className="pb-admin-kb-drawer-title">Edit metadata</DialogPrimitive.Title>
            <DialogPrimitive.Description className="sr-only">
              Update metadata used to organize and prioritize this knowledge-base document.
            </DialogPrimitive.Description>
            <DialogPrimitive.Close asChild>
              <button className="pb-admin-kb-icon-button ml-auto" type="button" aria-label="Close metadata drawer">
                <X size={17} />
              </button>
            </DialogPrimitive.Close>
          </div>
          <div className="pb-admin-kb-drawer-body">
            <div className="pb-admin-kb-detail-note">
              <span className="pb-admin-kb-detail-icon" aria-hidden="true">
                <FileText size={16} />
              </span>
              <span className="min-w-0 truncate">{document.title}</span>
            </div>
            <label>
              <span className="pb-admin-kb-field-label block">Metadata tags</span>
              <input className="pb-admin-kb-input" onChange={(event) => setTags(event.target.value)} value={tags} />
            </label>
            <label>
              <span className="pb-admin-kb-field-label block">Source date</span>
              <input className="pb-admin-kb-input" onChange={(event) => setSourceDate(event.target.value)} value={sourceDate} />
            </label>
          </div>
          <div className="pb-admin-kb-drawer-footer">
            {canManage && (
              <button className="pb-admin-kb-inline-action" onClick={() => onDelete(document.id)} type="button">
                <Trash2 size={15} />
                Delete
              </button>
            )}
            <div className="ml-auto flex gap-2">
              <Button onClick={onClose} size="sm" variant="secondary">
                Cancel
              </Button>
              <Button onClick={handleSave} size="sm">
                Save changes
              </Button>
            </div>
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}

function getTags(document: KBDocument): string[] {
  const topics = document.metadata_tags.topics
  if (!Array.isArray(topics)) return []
  return topics.filter((tag): tag is string => typeof tag === 'string' && tag.trim().length > 0)
}
