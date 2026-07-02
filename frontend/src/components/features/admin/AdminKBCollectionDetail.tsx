'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useDropzone, type FileRejection } from 'react-dropzone'
import { ArrowLeft, FileUp, Tags, Trash2 } from 'lucide-react'
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
import { Button, Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/src/components/ui'
import { validateUploadFile } from '@/src/lib/api/uploadValidation'
import type {
  KBCollectionViewModel,
  KBDocument,
  KBMetadataTag,
  UploadKBDocumentRequest,
} from '@/src/types/kb'

const KB_UPLOAD_DROPZONE_ACCEPT = {
  'application/pdf': ['.pdf'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['.pptx'],
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
} as const

interface AdminKBCollectionDetailProps {
  canDeleteCollection?: boolean
  canManage: boolean
  canManageTags?: boolean
  collection: KBCollectionViewModel
  metadataTags: KBMetadataTag[]
  onBack: () => void
  onDeleteCollection?: (collection: KBCollectionViewModel) => void
  onDelete: (id: string) => void
  onEdit: (id: string) => void
  onManageTags?: () => void
  onRetry: (id: string) => void
  onUpload: (request: UploadKBDocumentRequest) => Promise<KBDocument>
}

export function AdminKBCollectionDetail({
  canDeleteCollection = false,
  canManage,
  canManageTags = false,
  collection,
  metadataTags,
  onBack,
  onDeleteCollection,
  onDelete,
  onEdit,
  onManageTags,
  onRetry,
  onUpload,
}: AdminKBCollectionDetailProps) {
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false)
  const [selectedUploadFile, setSelectedUploadFile] = useState<File | null>(null)
  const [dropzoneError, setDropzoneError] = useState<string | null>(null)
  const [localUploads, setLocalUploads] = useState<AdminKBLocalUploadRow[]>([])
  const subtitle = `${collection.documents.length} ${collection.documents.length === 1 ? 'document' : 'documents'}`
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

  const openUploadDialog = useCallback((file: File) => {
    try {
      validateUploadFile(file)
      setDropzoneError(null)
      setSelectedUploadFile(file)
      setUploadDialogOpen(true)
    } catch (error) {
      setDropzoneError(getSafeUploadErrorMessage(error))
    }
  }, [])

  const handleRejectedFiles = useCallback((fileRejections: FileRejection[]) => {
    const rejectedFile = fileRejections[0]?.file
    if (!rejectedFile) {
      setDropzoneError('Choose a supported file to upload.')
      return
    }
    try {
      validateUploadFile(rejectedFile)
      setDropzoneError('Choose a supported file to upload.')
    } catch (error) {
      setDropzoneError(getSafeUploadErrorMessage(error))
    }
  }, [])

  const { getInputProps, getRootProps, isDragAccept, isDragActive, isDragReject } = useDropzone({
    accept: KB_UPLOAD_DROPZONE_ACCEPT,
    disabled: !canManage,
    multiple: false,
    onDrop: (acceptedFiles, fileRejections) => {
      if (fileRejections.length > 0) {
        handleRejectedFiles(fileRejections)
        return
      }
      const file = acceptedFiles[0]
      if (file) openUploadDialog(file)
    },
  })

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

  const handleUploadDialogOpenChange = (open: boolean) => {
    setUploadDialogOpen(open)
    if (!open) setSelectedUploadFile(null)
  }

  return (
    <AdminPageScaffold
      actions={
        <>
          <Button className="pb-admin-header-control" onClick={onBack} size="sm" variant="secondary">
            <ArrowLeft size={15} />
            All collections
          </Button>
          {canManageTags && onManageTags && (
            <Button className="pb-admin-header-control" onClick={onManageTags} size="sm" variant="secondary">
              <Tags size={15} />
              Manage tags
            </Button>
          )}
          {canDeleteCollection && onDeleteCollection && (
            <CollectionDeleteButton
              collection={collection}
              onDeleteCollection={() => onDeleteCollection(collection)}
            />
          )}
        </>
      }
      contentClassName="py-6"
      contentMaxWidthClassName="pb-admin-kb-detail-width"
      subtitle={subtitle}
      title={collection.title}
    >
      <div className="pb-admin-kb-detail-note">
        <span className="pb-admin-kb-detail-icon" aria-hidden="true">
          <Icon size={17} />
        </span>
        <span>{collection.description}</span>
      </div>
      {canManage && (
        <div className="mb-4">
          <section aria-label="Document upload" className="pb-admin-kb-upload-panel">
            <h2 className="pb-admin-kb-upload-title">Upload documents</h2>
            <div
              {...getRootProps({
                'aria-label': `Upload knowledge-base document to ${collection.title}`,
                className: 'pb-admin-kb-dropzone',
                'data-accept': isDragAccept,
                'data-active': isDragActive,
                'data-reject': isDragReject,
                role: 'button',
              })}
            >
              <input {...getInputProps({ 'aria-label': 'Upload knowledge-base document' })} />
              <span className="pb-admin-kb-dropzone-icon" aria-hidden="true">
                <FileUp size={22} />
              </span>
              <span className="pb-admin-kb-dropzone-content">
                <span className="pb-admin-kb-dropzone-title">
                  {isDragActive ? 'Drop document here' : 'Drag and Drop here'}
                </span>
                <span className="pb-admin-kb-dropzone-separator">or</span>
                <span className="pb-admin-kb-dropzone-browse">Browse files</span>
                <span className="pb-admin-kb-upload-accepted">
                  Accepted file types: PDF, DOCX, PPTX, or XLSX.
                </span>
                <span className="pb-admin-kb-upload-accepted">
                  Only upload department-approved content.
                </span>
              </span>
            </div>
          </section>
          {dropzoneError && (
            <p className="pb-admin-table-text mt-2 rounded-md border border-danger/30 bg-danger-bg px-3 py-2 text-danger">
              {dropzoneError}
            </p>
          )}
        </div>
      )}
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
        initialFile={selectedUploadFile}
        metadataTags={metadataTags}
        onOpenChange={handleUploadDialogOpenChange}
        onSubmit={startUpload}
        open={uploadDialogOpen}
      />
    </AdminPageScaffold>
  )
}

interface CollectionDeleteButtonProps {
  collection: KBCollectionViewModel
  onDeleteCollection: () => void
}

function CollectionDeleteButton({
  collection,
  onDeleteCollection,
}: CollectionDeleteButtonProps) {
  const hasDocuments = collection.documents.length > 0
  const button = (
    <Button
      aria-disabled={hasDocuments}
      className="pb-admin-header-control"
      disabled={hasDocuments}
      onClick={onDeleteCollection}
      size="sm"
      variant="secondary"
    >
      <Trash2 size={15} />
      Delete collection
    </Button>
  )

  if (!hasDocuments) return button

  return (
    <TooltipProvider delayDuration={150}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="inline-flex cursor-not-allowed">{button}</span>
        </TooltipTrigger>
        <TooltipContent>
          Delete the documents in this collection first.
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

function uploadKey(filename: string, sizeBytes: number): string {
  return `${filename}:${sizeBytes}`
}
