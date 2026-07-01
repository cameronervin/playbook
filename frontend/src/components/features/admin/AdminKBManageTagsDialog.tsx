'use client'

import { useMemo, useState, type FormEvent, type ReactNode } from 'react'
import { Archive, Check, Pencil, Plus, RotateCcw, Trash2, X } from 'lucide-react'
import {
  Button,
  Dialog,
  Input,
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/src/components/ui'
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
  onDeletePermanently: (tagId: string) => Promise<unknown>
  onOpenChange: (open: boolean) => void
  onUnarchive: (tagId: string) => Promise<unknown>
  onUpdate: (tagId: string, request: KBMetadataTagUpdateRequest) => Promise<unknown>
  open: boolean
  tagUsageCounts?: ReadonlyMap<string, number>
  tags: KBMetadataTag[]
}

interface TagSectionProps {
  children: ReactNode
  emptyMessage: string
  title: string
}

export function AdminKBManageTagsDialog({
  isBusy = false,
  onArchive,
  onCreate,
  onDeletePermanently,
  onOpenChange,
  onUnarchive,
  onUpdate,
  open,
  tagUsageCounts,
  tags,
}: AdminKBManageTagsDialogProps) {
  const [newLabel, setNewLabel] = useState('')
  const [editingTagId, setEditingTagId] = useState<string | null>(null)
  const [editingLabel, setEditingLabel] = useState('')
  const [pendingTagId, setPendingTagId] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const activeTags = useMemo(() => tags.filter((tag) => tag.is_active), [tags])
  const archivedTags = useMemo(() => tags.filter((tag) => !tag.is_active), [tags])

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

  const unarchiveTag = async (tag: KBMetadataTag) => {
    setErrorMessage(null)
    setPendingTagId(tag.id)
    try {
      await onUnarchive(tag.id)
    } catch (error) {
      setErrorMessage(getSafeUploadErrorMessage(error))
    } finally {
      setPendingTagId(null)
    }
  }

  const permanentlyDeleteTag = async (tag: KBMetadataTag) => {
    if ((tagUsageCounts?.get(tag.slug) ?? 0) > 0) return
    setErrorMessage(null)
    setPendingTagId(tag.id)
    try {
      await onDeletePermanently(tag.id)
    } catch (error) {
      setErrorMessage(getSafeUploadErrorMessage(error))
    } finally {
      setPendingTagId(null)
    }
  }

  return (
    <Dialog
      className="pb-admin-kb-tags-dialog"
      description="Create, rename, archive, restore, and delete preset metadata tags admins can assign to documents."
      onOpenChange={onOpenChange}
      open={open}
      title="Manage tags"
    >
      <TooltipProvider>
        <div className="flex flex-col gap-4">
          <form className="flex gap-2" onSubmit={handleCreate}>
            <label className="min-w-0 flex-1">
              <span className="sr-only">New metadata tag label</span>
              <Input
                className="pb-admin-kb-tag-create-input"
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
          {errorMessage && (
            <p className="pb-admin-table-text rounded-md border border-danger/30 bg-danger-bg px-3 py-2 text-danger">
              {errorMessage}
            </p>
          )}
          <TagSection emptyMessage="No active tags." title="Active tags">
            {activeTags.map((tag) => {
              const isEditing = editingTagId === tag.id
              const isPending = pendingTagId === tag.id
              return (
                <span className="pb-admin-kb-managed-tag" key={tag.id}>
                  {isEditing ? (
                    <input
                      aria-label={`Edit ${tag.label}`}
                      className="pb-admin-kb-managed-tag-input"
                      onChange={(event) => setEditingLabel(event.target.value)}
                      value={editingLabel}
                    />
                  ) : (
                    <span className="pb-admin-kb-managed-tag-label">{tag.label}</span>
                  )}
                  <span className="pb-admin-kb-managed-tag-actions">
                    {isEditing ? (
                      <>
                        <button
                          aria-label={`Save ${tag.label}`}
                          className="pb-admin-kb-tag-icon"
                          disabled={isBusy || isPending}
                          onClick={() => void saveEdit(tag)}
                          type="button"
                        >
                          <Check size={12} />
                        </button>
                        <button
                          aria-label="Cancel tag edit"
                          className="pb-admin-kb-tag-icon"
                          disabled={isBusy || isPending}
                          onClick={() => setEditingTagId(null)}
                          type="button"
                        >
                          <X size={12} />
                        </button>
                      </>
                    ) : (
                      <>
                        <button
                          aria-label={`Rename ${tag.label}`}
                          className="pb-admin-kb-tag-icon"
                          disabled={isBusy || isPending}
                          onClick={() => startEdit(tag)}
                          type="button"
                        >
                          <Pencil size={12} />
                        </button>
                        <button
                          aria-label={`Archive ${tag.label}`}
                          className="pb-admin-kb-tag-add"
                          disabled={isBusy || isPending}
                          onClick={() => void archiveTag(tag)}
                          type="button"
                        >
                          <Archive size={12} />
                        </button>
                      </>
                    )}
                  </span>
                </span>
              )
            })}
          </TagSection>
          <TagSection emptyMessage="No archived tags." title="Archived tags">
            {archivedTags.map((tag) => {
              const isPending = pendingTagId === tag.id
              const usageCount = tagUsageCounts?.get(tag.slug) ?? 0
              const deleteDisabled = isBusy || isPending || usageCount > 0
              const usageText = usageCount === 1 ? '1 document' : `${usageCount} documents`
              const deleteButton = (
                <button
                  aria-label={
                    usageCount > 0
                      ? `Delete ${tag.label} permanently - remove from ${usageText} first`
                      : `Delete ${tag.label} permanently`
                  }
                  className="pb-admin-kb-tag-icon"
                  disabled={deleteDisabled}
                  onClick={() => void permanentlyDeleteTag(tag)}
                  type="button"
                >
                  <Trash2 size={12} />
                </button>
              )
              return (
                <span className="pb-admin-kb-managed-tag" data-archived="true" key={tag.id}>
                  <span className="pb-admin-kb-managed-tag-label">{tag.label}</span>
                  <span className="pb-admin-kb-managed-tag-actions">
                    <button
                      aria-label={`Unarchive ${tag.label}`}
                      className="pb-admin-kb-tag-add"
                      disabled={isBusy || isPending}
                      onClick={() => void unarchiveTag(tag)}
                      type="button"
                    >
                      <RotateCcw size={12} />
                    </button>
                    {usageCount > 0 ? (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span className="inline-flex">{deleteButton}</span>
                        </TooltipTrigger>
                        <TooltipContent>
                          Remove this tag from {usageText} before deleting it.
                        </TooltipContent>
                      </Tooltip>
                    ) : (
                      deleteButton
                    )}
                  </span>
                </span>
              )
            })}
          </TagSection>
        </div>
      </TooltipProvider>
    </Dialog>
  )
}

function TagSection({ children, emptyMessage, title }: TagSectionProps) {
  const hasTags = Array.isArray(children) ? children.length > 0 : Boolean(children)
  return (
    <section className="pb-admin-kb-tag-section" aria-label={title}>
      <h3 className="pb-admin-kb-field-label">{title}</h3>
      <div className="pb-admin-kb-managed-tags">
        {hasTags ? children : <span className="pb-admin-kb-tag-empty">{emptyMessage}</span>}
      </div>
    </section>
  )
}
