'use client'

import { useEffect, useMemo, useState } from 'react'
import { ArrowLeft, Upload } from 'lucide-react'
import { AdminKBDocumentRow } from '@/src/components/features/admin/AdminKBDocumentRow'
import { AdminKBLocalUploadRowView } from '@/src/components/features/admin/AdminKBLocalUploadRow'
import { AdminPageScaffold } from '@/src/components/features/admin/AdminPageScaffold'
import { AdminKBUploadDialog } from '@/src/components/features/admin/AdminKBUploadDialog'
import {
  COLLECTION_ICON_COMPONENTS,
  getSafeUploadErrorMessage,
  type AdminKBUploadRetryRequest,
  type AdminKBLocalUploadRow,
} from '@/src/components/features/admin/kbFormatting'
import { Button } from '@/src/components/ui'
import { validateUploadFile } from '@/src/lib/api/uploadValidation'
import type { KBCollectionViewModel, KBDocument, UploadKBDocumentRequest } from '@/src/types/kb'

interface AdminKBCollectionDetailProps {
  canManage: boolean
  collection: KBCollectionViewModel
  onBack: () => void
  onDelete: (id: string) => void
  onEdit: (id: string) => void
  onRetry: (id: string) => void
  onUpload: (request: UploadKBDocumentRequest) => Promise<KBDocument>
}

export function AdminKBCollectionDetail({
  canManage,
  collection,
  onBack,
  onDelete,
  onEdit,
  onRetry,
  onUpload,
}: AdminKBCollectionDetailProps) {
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false)
  const [localUploads, setLocalUploads] = useState<AdminKBLocalUploadRow[]>([])
  const subtitle = `${collection.documents.length} ${collection.documents.length === 1 ? 'document' : 'documents'} · grounds athlete answers`
  const Icon = COLLECTION_ICON_COMPONENTS[collection.icon]
  const serverDocumentUploadKeys = useMemo(
    () => new Set(collection.documents.map((document) => uploadKey(document.filename, document.size_bytes))),
    [collection.documents],
  )

  useEffect(() => {
    setLocalUploads((current) =>
      current.filter((upload) => {
        if (upload.phase !== 'queued') return true
        return !serverDocumentUploadKeys.has(uploadKey(upload.file.name, upload.file.size))
      }),
    )
  }, [serverDocumentUploadKeys])

  const startUpload = (request: AdminKBUploadRetryRequest) => {
    const id = `${request.file.name}-${request.file.lastModified}-${Date.now()}`
    try {
      validateUploadFile(request.file)
    } catch (error) {
      setLocalUploads((current) => [
        {
          errorMessage: getSafeUploadErrorMessage(error),
          file: request.file,
          id,
          percent: 0,
          phase: 'failed',
          request,
        },
        ...current,
      ])
      return
    }

    setLocalUploads((current) => [
      { file: request.file, id, percent: 0, phase: 'requesting', request },
      ...current,
    ])
    void onUpload({
      ...request,
      onProgress: (progress) => {
        setLocalUploads((current) =>
          current.map((upload) =>
            upload.id === id
              ? { ...upload, percent: progress.percent, phase: 'uploading' }
              : upload,
          ),
        )
      },
    })
      .then(() => {
        setLocalUploads((current) =>
          current.map((upload) =>
            upload.id === id ? { ...upload, percent: 100, phase: 'queued' } : upload,
          ),
        )
      })
      .catch((error: unknown) => {
        setLocalUploads((current) =>
          current.map((upload) =>
            upload.id === id
              ? {
                  ...upload,
                  errorMessage: getSafeUploadErrorMessage(error),
                  phase: 'failed',
                }
              : upload,
          ),
        )
      })
  }

  return (
    <AdminPageScaffold
      actions={
        <>
          <Button className="pb-admin-header-control" onClick={onBack} size="sm" variant="secondary">
            <ArrowLeft size={15} />
            All collections
          </Button>
          {canManage && (
            <Button className="pb-admin-header-control" onClick={() => setUploadDialogOpen(true)} size="sm">
              <Upload size={15} />
              Upload document
            </Button>
          )}
        </>
      }
      contentClassName="py-6"
      contentMaxWidthClassName="pb-admin-kb-detail-width"
      subtitle={subtitle}
      title={collection.name}
    >
      <div className="pb-admin-kb-detail-note">
        <span className="pb-admin-kb-detail-icon" aria-hidden="true">
          <Icon size={17} />
        </span>
        <span>{collection.blurb}</span>
      </div>
      {localUploads.length > 0 && (
        <div className="pb-admin-kb-doc-list mb-3">
          {localUploads.map((upload) => (
            <AdminKBLocalUploadRowView
              key={upload.id}
              onRetry={() => startUpload(upload.request)}
              upload={upload}
            />
          ))}
        </div>
      )}
      {collection.documents.length === 0 && localUploads.length === 0 ? (
        <div className="pb-admin-kb-detail-note">
          No documents yet{canManage ? '. Upload department documents to start grounding answers from this collection.' : '.'}
        </div>
      ) : (
        <div className="pb-admin-kb-doc-list">
          {collection.documents.map((document) => (
            <AdminKBDocumentRow
              canManage={canManage}
              document={document}
              key={document.id}
              onDelete={() => onDelete(document.id)}
              onEdit={() => onEdit(document.id)}
              onRetry={() => onRetry(document.id)}
            />
          ))}
        </div>
      )}
      <AdminKBUploadDialog
        collection={collection}
        onOpenChange={setUploadDialogOpen}
        onSubmit={startUpload}
        open={uploadDialogOpen}
      />
    </AdminPageScaffold>
  )
}

function uploadKey(filename: string, sizeBytes: number): string {
  return `${filename}:${sizeBytes}`
}
