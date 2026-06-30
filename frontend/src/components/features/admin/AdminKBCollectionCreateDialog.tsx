'use client'

import { useEffect, useState, type FormEvent } from 'react'
import { Check, Plus } from 'lucide-react'
import { Button, Dialog, Input } from '@/src/components/ui'
import {
  COLLECTION_ICON_COMPONENTS,
  getSafeUploadErrorMessage,
} from '@/src/components/features/admin/kbFormatting'
import { cn } from '@/src/lib/utils/cn'
import type { KBCollectionCreateRequest, KBCollectionIcon } from '@/src/types/kb'

const ICON_OPTIONS: Array<{ icon: KBCollectionIcon; label: string }> = [
  { icon: 'shield', label: 'Shield' },
  { icon: 'plane', label: 'Travel' },
  { icon: 'book-open', label: 'Book' },
  { icon: 'users', label: 'People' },
  { icon: 'database', label: 'Database' },
]

interface AdminKBCollectionCreateDialogProps {
  onCreate: (request: KBCollectionCreateRequest) => Promise<unknown>
  onOpenChange: (open: boolean) => void
  open: boolean
}

export function AdminKBCollectionCreateDialog({
  onCreate,
  onOpenChange,
  open,
}: AdminKBCollectionCreateDialogProps) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [icon, setIcon] = useState<KBCollectionIcon>('shield')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)

  useEffect(() => {
    if (!open) return
    setTitle('')
    setDescription('')
    setIcon('shield')
    setErrorMessage(null)
    setIsSaving(false)
  }, [open])

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const normalizedTitle = title.trim()
    const normalizedDescription = description.trim()
    if (!normalizedTitle || !normalizedDescription) {
      setErrorMessage('Title and description are required.')
      return
    }
    setErrorMessage(null)
    setIsSaving(true)
    try {
      await onCreate({
        description: normalizedDescription,
        icon,
        title: normalizedTitle,
      })
      onOpenChange(false)
    } catch (error) {
      setErrorMessage(getSafeUploadErrorMessage(error))
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <Dialog
      description="Create a department knowledge-base collection admins can upload documents into."
      onOpenChange={onOpenChange}
      open={open}
      title="New collection"
    >
      <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
        <label>
          <span className="pb-admin-kb-field-label block">Title</span>
          <Input
            autoFocus
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Compliance & NIL"
            value={title}
          />
        </label>
        <label>
          <span className="pb-admin-kb-field-label block">Description</span>
          <Input
            onChange={(event) => setDescription(event.target.value)}
            placeholder="Policies, procedures, and source documents for this collection."
            value={description}
          />
        </label>
        <fieldset>
          <legend className="pb-admin-kb-field-label block">Icon</legend>
          <div className="pb-admin-kb-icon-options">
            {ICON_OPTIONS.map((option) => {
              const Icon = COLLECTION_ICON_COMPONENTS[option.icon]
              const selected = icon === option.icon
              return (
                <button
                  aria-pressed={selected}
                  className={cn('pb-admin-kb-icon-option', selected && 'is-selected')}
                  key={option.icon}
                  onClick={() => setIcon(option.icon)}
                  type="button"
                >
                  <Icon size={16} />
                  <span>{option.label}</span>
                  {selected && <Check size={13} />}
                </button>
              )
            })}
          </div>
        </fieldset>
        {errorMessage && (
          <p className="pb-admin-table-text rounded-md border border-danger/30 bg-danger-bg px-3 py-2 text-danger">
            {errorMessage}
          </p>
        )}
        <div className="mt-1 flex justify-end gap-2">
          <Button onClick={() => onOpenChange(false)} size="sm" type="button" variant="secondary">
            Cancel
          </Button>
          <Button disabled={isSaving} size="sm" type="submit">
            <Plus size={15} />
            {isSaving ? 'Creating...' : 'Create collection'}
          </Button>
        </div>
      </form>
    </Dialog>
  )
}
