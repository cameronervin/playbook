'use client'

import { useRef, useState, type ChangeEvent } from 'react'
import { ArrowLeft, Upload } from 'lucide-react'
import { AdminKBDocumentRow } from '@/src/components/features/admin/AdminKBDocumentRow'
import { AdminKBLocalUploadRowView } from '@/src/components/features/admin/AdminKBLocalUploadRow'
import { AdminPageScaffold } from '@/src/components/features/admin/AdminPageScaffold'
import {
  COLLECTION_ICON_COMPONENTS,
  getSafeUploadErrorMessage,
  type AdminKBLocalUploadRow,
} from '@/src/components/features/admin/kbFormatting'
import { Button } from '@/src/components/ui'
import { validateUploadFile } from '@/src/lib/api/uploadValidation'
import { SUPPORTED_UPLOAD_ACCEPT } from '@/src/lib/constants/uploads'
import { collectionUploadMetadata } from '@/src/lib/fixtures/kbCollections'
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
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [localUploads, setLocalUploads] = useState<AdminKBLocalUploadRow[]>([])
  const subtitle = `${collection.documents.length} ${collection.documents.length === 1 ? 'document' : 'documents'} · grounds athlete answers`
  const Icon = COLLECTION_ICON_COMPONENTS[collection.icon]

  const startUpload = (file: File) => {
    const id = `${file.name}-${file.lastModified}-${Date.now()}`
    try {
      validateUploadFile(file)
    } catch (error) {
      setLocalUploads((current) => [
        {
          errorMessage: getSafeUploadErrorMessage(error),
          file,
          id,
          percent: 0,
          phase: 'failed',
        },
        ...current,
      ])
      return
    }

    setLocalUploads((current) => [
      { file, id, percent: 0, phase: 'requesting' },
      ...current,
    ])
    void onUpload({
      file,
      metadata_tags: collectionUploadMetadata(collection),
      onProgress: (progress) => {
        setLocalUploads((current) =>
          current.map((upload) =>
            upload.id === id
              ? { ...upload, percent: progress.percent, phase: 'uploading' }
              : upload,
          ),
        )
      },
      title: file.name,
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

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    startUpload(file)
    event.target.value = ''
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
            <>
              <input
                accept={SUPPORTED_UPLOAD_ACCEPT}
                aria-label="Upload document file"
                className="sr-only"
                onChange={handleFileChange}
                ref={fileInputRef}
                type="file"
              />
              <Button className="pb-admin-header-control" onClick={() => fileInputRef.current?.click()} size="sm">
                <Upload size={15} />
                Upload document
              </Button>
            </>
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
              onRetry={() => startUpload(upload.file)}
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
    </AdminPageScaffold>
  )
}
