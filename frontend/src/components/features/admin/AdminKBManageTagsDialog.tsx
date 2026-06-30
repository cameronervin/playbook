'use client'

import { useMemo, useState, type FormEvent } from 'react'
import { Archive, Check, Pencil, Plus, Search, X } from 'lucide-react'
import { Button, Dialog, Input } from '@/src/components/ui'
import { getSafeUploadErrorMessage } from '@/src/components/features/admin/kbFormatting'
import type {
  KBMetadataTag,
  KBMetadataTagCreateRequest,
  KBMetadataTagUpdateRequest,
} from '@/src/types/kb'

interface AdminKBManageTagsDialogProps {
  isBusy?: boolean
  onArchive: (tagId: string) => Promise<unknown>
  onCreate: (request: KBMetadataTagCreateRequest) => Promise<unknown>
  onOpenChange: (open: boolean) => void
  onUpdate: (tagId: string, request: KBMetadataTagUpdateRequest) => Promise<unknown>
  open: boolean
  tags: KBMetadataTag[]
}

export function AdminKBManageTagsDialog({
  isBusy = false,
  onArchive,
  onCreate,
  onOpenChange,
  onUpdate,
  open,
  tags,
}: AdminKBManageTagsDialogProps) {
  const [query, setQuery] = useState('')
  const [newLabel, setNewLabel] = useState('')
  const [editingTagId, setEditingTagId] = useState<string | null>(null)
  const [editingLabel, setEditingLabel] = useState('')
  const [pendingTagId, setPendingTagId] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const normalizedQuery = query.trim().toLowerCase()
  const filteredTags = useMemo(
    () =>
      tags.filter((tag) =>
        normalizedQuery
          ? tag.label.toLowerCase().includes(normalizedQuery) ||
            tag.slug.toLowerCase().includes(normalizedQuery)
          : true,
      ),
    [normalizedQuery, tags],
  )

  const handleCreate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const label = newLabel.trim()
    if (!label) {
      setErrorMessage('Enter a tag label.')
      return
    }
    setErrorMessage(null)
    setPendingTagId('new')
    try {
      await onCreate({ label })
      setNewLabel('')
    } catch (error) {
      setErrorMessage(getSafeUploadErrorMessage(error))
    } finally {
      setPendingTagId(null)
    }
  }

  const startEdit = (tag: KBMetadataTag) => {
    setEditingTagId(tag.id)
    setEditingLabel(tag.label)
    setErrorMessage(null)
  }

  const saveEdit = async (tag: KBMetadataTag) => {
    const label = editingLabel.trim()
    if (!label) {
      setErrorMessage('Enter a tag label.')
      return
    }
    setErrorMessage(null)
    setPendingTagId(tag.id)
    try {
      await onUpdate(tag.id, { label })
      setEditingTagId(null)
      setEditingLabel('')
    } catch (error) {
      setErrorMessage(getSafeUploadErrorMessage(error))
    } finally {
      setPendingTagId(null)
    }
  }

  const archiveTag = async (tag: KBMetadataTag) => {
    setErrorMessage(null)
    setPendingTagId(tag.id)
    try {
      await onArchive(tag.id)
    } catch (error) {
      setErrorMessage(getSafeUploadErrorMessage(error))
    } finally {
      setPendingTagId(null)
    }
  }

  return (
    <Dialog
      className="pb-admin-kb-tags-dialog"
      description="Create, rename, and archive the preset metadata tags admins can assign to documents."
      onOpenChange={onOpenChange}
      open={open}
      title="Manage tags"
    >
      <div className="flex flex-col gap-4">
        <form className="flex gap-2" onSubmit={handleCreate}>
          <label className="min-w-0 flex-1">
            <span className="sr-only">New metadata tag label</span>
            <Input
              disabled={isBusy || pendingTagId === 'new'}
              onChange={(event) => setNewLabel(event.target.value)}
              placeholder="Add tag label"
              value={newLabel}
            />
          </label>
          <Button disabled={isBusy || pendingTagId === 'new'} size="sm" type="submit">
            <Plus size={15} />
            Add
          </Button>
        </form>
        <label>
          <span className="pb-admin-kb-field-label block">Search tags</span>
          <span className="relative block">
            <Search
              aria-hidden="true"
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-fg-4"
              size={15}
            />
            <Input
              className="pl-9"
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search by label or slug"
              value={query}
            />
          </span>
        </label>
        {errorMessage && (
          <p className="pb-admin-table-text rounded-md border border-danger/30 bg-danger-bg px-3 py-2 text-danger">
            {errorMessage}
          </p>
        )}
        <div className="pb-admin-kb-tag-list">
          {filteredTags.length > 0 ? (
            filteredTags.map((tag) => {
              const isEditing = editingTagId === tag.id
              const isPending = pendingTagId === tag.id
              return (
                <div className="pb-admin-kb-tag-row" data-archived={!tag.is_active} key={tag.id}>
                  {isEditing ? (
                    <input
                      aria-label={`Edit ${tag.label}`}
                      className="pb-admin-kb-input"
                      onChange={(event) => setEditingLabel(event.target.value)}
                      value={editingLabel}
                    />
                  ) : (
                    <div className="min-w-0 flex-1">
                      <div className="pb-admin-kb-tag-row-label">{tag.label}</div>
                      <div className="pb-admin-kb-tag-row-slug">{tag.slug}</div>
                    </div>
                  )}
                  {!tag.is_active && (
                    <span className="pb-admin-kb-tag-row-status">
                      <Archive size={12} />
                      Archived
                    </span>
                  )}
                  <div className="ml-auto flex items-center gap-1">
                    {isEditing ? (
                      <>
                        <button
                          aria-label={`Save ${tag.label}`}
                          className="pb-admin-kb-icon-button"
                          disabled={isBusy || isPending}
                          onClick={() => void saveEdit(tag)}
                          type="button"
                        >
                          <Check size={15} />
                        </button>
                        <button
                          aria-label="Cancel tag edit"
                          className="pb-admin-kb-icon-button"
                          disabled={isBusy || isPending}
                          onClick={() => setEditingTagId(null)}
                          type="button"
                        >
                          <X size={15} />
                        </button>
                      </>
                    ) : (
                      <button
                        aria-label={`Rename ${tag.label}`}
                        className="pb-admin-kb-icon-button"
                        disabled={isBusy || isPending}
                        onClick={() => startEdit(tag)}
                        type="button"
                      >
                        <Pencil size={15} />
                      </button>
                    )}
                    {tag.is_active && !isEditing && (
                      <button
                        aria-label={`Archive ${tag.label}`}
                        className="pb-admin-kb-icon-button"
                        disabled={isBusy || isPending}
                        onClick={() => void archiveTag(tag)}
                        type="button"
                      >
                        <Archive size={15} />
                      </button>
                    )}
                  </div>
                </div>
              )
            })
          ) : (
            <div className="pb-admin-kb-tag-empty">No tags match that search.</div>
          )}
        </div>
      </div>
    </Dialog>
  )
}
