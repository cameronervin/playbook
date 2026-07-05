'use client'

import { useEffect, useState } from 'react'
import { Trash2 } from 'lucide-react'
import { getSafeUploadErrorMessage } from '@/src/components/features/admin/kbFormatting'
import { Button, Dialog } from '@/src/components/ui'
import type { KBCollectionViewModel } from '@/src/types/kb'

interface AdminKBCollectionDeleteDialogProps {
  collection: KBCollectionViewModel | null
  onClose: () => void
  onDelete: (collectionId: string) => Promise<unknown>
  onDeleted: (collectionId: string) => void
}

export function AdminKBCollectionDeleteDialog({
  collection,
  onClose,
  onDelete,
  onDeleted,
}: AdminKBCollectionDeleteDialogProps) {
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)

  useEffect(() => {
    if (!collection) return
    setErrorMessage(null)
    setIsDeleting(false)
  }, [collection])

  const handleDelete = async () => {
    if (!collection || collection.documents.length > 0) return
    setErrorMessage(null)
    setIsDeleting(true)
    try {
      await onDelete(collection.id)
      onDeleted(collection.id)
      onClose()
    } catch (error) {
      setErrorMessage(getSafeUploadErrorMessage(error))
    } finally {
      setIsDeleting(false)
    }
  }

  return (
    <Dialog
      description={
        collection
          ? `Delete ${collection.title}? This removes the empty collection from active knowledge-base management.`
          : undefined
      }
      onOpenChange={(open) => {
        if (!open) onClose()
      }}
      open={Boolean(collection)}
      title="Delete collection"
    >
      {collection && (
        <div className="space-y-4">
          <div className="pb-admin-kb-detail-note mb-0">
            <span className="pb-admin-kb-detail-icon" aria-hidden="true">
              <Trash2 size={16} />
            </span>
            <span className="min-w-0 truncate">{collection.title}</span>
          </div>
          {errorMessage && (
            <p className="pb-admin-table-text rounded-md border border-danger/30 bg-danger-bg px-3 py-2 text-danger">
              {errorMessage}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button onClick={onClose} size="sm" type="button" variant="secondary">
              Cancel
            </Button>
            <Button disabled={isDeleting} onClick={handleDelete} size="sm" type="button" variant="danger">
              <Trash2 size={15} />
              {isDeleting ? 'Deleting...' : 'Delete collection'}
            </Button>
          </div>
        </div>
      )}
    </Dialog>
  )
}
