'use client'

import { useMemo, useRef, useState, type ChangeEvent } from 'react'
import {
  AlertTriangle,
  ArrowLeft,
  BookOpen,
  ChevronRight,
  Database,
  FileText,
  LoaderCircle,
  Lock,
  Plane,
  Plus,
  RefreshCw,
  Shield,
  Upload,
  Users,
} from 'lucide-react'
import { AdminKBDocumentRow } from '@/src/components/features/admin/AdminKBDocumentRow'
import { AdminKBMetadataDrawer } from '@/src/components/features/admin/AdminKBMetadataDrawer'
import { AdminPageScaffold } from '@/src/components/features/admin/AdminPageScaffold'
import { AdminKBSkeleton } from '@/src/components/features/loading/PlaybookLoaders'
import { Button } from '@/src/components/ui'
import { validateUploadFile } from '@/src/lib/api/uploadValidation'
import { SUPPORTED_UPLOAD_ACCEPT } from '@/src/lib/constants/uploads'
import { ADMIN_KB_COLLECTIONS, buildKBCollectionViews, collectionUploadMetadata } from '@/src/lib/fixtures/kbCollections'
import type { UploadKBDocumentRequest } from '@/src/types/kb'
import type { KBCollection, KBCollectionIcon, KBCollectionViewModel, KBDocument, KBDocumentMetadataUpdateRequest } from '@/src/types/kb'

interface AdminKnowledgeBasePanelProps {
  canManage: boolean
  documents: KBDocument[]
  isError?: boolean
  isFetching?: boolean
  isLoading?: boolean
  onDelete: (id: string) => void
  onRetry: (id: string) => void
  onToggleOfficial: (id: string, isOfficial: boolean) => void
  onUpdateMetadata: (documentId: string, metadata: KBDocumentMetadataUpdateRequest) => void
  onUpload: (request: UploadKBDocumentRequest) => Promise<KBDocument>
}

export function AdminKnowledgeBasePanel({
  canManage,
  documents,
  isError = false,
  isFetching = false,
  isLoading = false,
  onDelete,
  onRetry,
  onToggleOfficial,
  onUpdateMetadata,
  onUpload,
}: AdminKnowledgeBasePanelProps) {
  const [extraCollections, setExtraCollections] = useState<KBCollection[]>([])
  const [openId, setOpenId] = useState<string | null>(null)
  const [editingDocumentId, setEditingDocumentId] = useState<string | null>(null)
  const collections = useMemo(() => [...ADMIN_KB_COLLECTIONS, ...extraCollections], [extraCollections])
  const collectionViews = useMemo(() => buildKBCollectionViews(documents, collections), [collections, documents])
  const openCollection = openId ? collectionViews.find((collection) => collection.id === openId) : null
  const editingDocument = editingDocumentId ? documents.find((document) => document.id === editingDocumentId) ?? null : null

  const handleCreateCollection = () => {
    const id = `collection-${extraCollections.length + 1}`
    const collection: KBCollection = {
      id,
      name: 'New collection',
      icon: 'database',
      blurb: 'Add documents to start grounding answers from this collection.',
      keywords: [id],
    }
    setExtraCollections((current) => [...current, collection])
    setOpenId(id)
  }

  if (openCollection) {
    return (
      <>
        <CollectionDetail
          canManage={canManage}
          collection={openCollection}
          onBack={() => setOpenId(null)}
          onDelete={onDelete}
          onEdit={setEditingDocumentId}
          onRetry={onRetry}
          onToggleOfficial={onToggleOfficial}
          onUpload={onUpload}
        />
        <AdminKBMetadataDrawer
          canManage={canManage}
          document={editingDocument}
          onClose={() => setEditingDocumentId(null)}
          onDelete={onDelete}
          onSave={onUpdateMetadata}
        />
      </>
    )
  }

  return (
    <CollectionGrid
      canManage={canManage}
      collections={collectionViews}
      isError={isError}
      isFetching={isFetching}
      isLoading={isLoading}
      onCreateCollection={handleCreateCollection}
      onOpen={setOpenId}
    />
  )
}

interface CollectionGridProps {
  canManage: boolean
  collections: KBCollectionViewModel[]
  isError: boolean
  isFetching: boolean
  isLoading: boolean
  onCreateCollection: () => void
  onOpen: (id: string) => void
}

function CollectionGrid({ canManage, collections, isError, isFetching, isLoading, onCreateCollection, onOpen }: CollectionGridProps) {
  const totalDocuments = collections.reduce((count, collection) => count + collection.documents.length, 0)

  return (
    <AdminPageScaffold
      actions={
        canManage ? (
          <Button className="pb-admin-header-control" onClick={onCreateCollection} size="sm" variant="secondary">
            <Plus size={15} />
            New collection
          </Button>
        ) : (
          <span className="pb-admin-kb-lock-note">
            <Lock size={14} />
            Managed by super admins
          </span>
        )
      }
      contentClassName="py-7"
      contentMaxWidthClassName="pb-admin-kb-grid-width"
      subtitle={isLoading ? undefined : `${totalDocuments} ${totalDocuments === 1 ? 'document' : 'documents'} across ${collections.length} collections`}
      title="Knowledge base"
    >
      {isLoading ? (
        <AdminKBSkeleton />
      ) : (
        <>
          {isFetching && (
            <p className="pb-refresh-note mb-3">
              <span className="pb-spin h-2 w-2 rounded-full border border-info border-t-transparent" />
              Refreshing knowledge base
            </p>
          )}
          {isError && (
            <p className="mb-3 rounded-md border border-danger/30 bg-danger-bg px-3 py-2 text-sm text-danger">
              Knowledge-base documents could not be refreshed.
            </p>
          )}
          <div className="pb-admin-kb-grid">
            {collections.map((collection) => (
              <CollectionCard collection={collection} key={collection.id} onOpen={() => onOpen(collection.id)} />
            ))}
          </div>
        </>
      )}
    </AdminPageScaffold>
  )
}

interface CollectionCardProps {
  collection: KBCollectionViewModel
  onOpen: () => void
}

function CollectionCard({ collection, onOpen }: CollectionCardProps) {
  return (
    <button
      className="pb-admin-kb-card"
      onClick={onOpen}
      type="button"
      aria-label={`${collection.name} collection`}
    >
      <div className="pb-admin-kb-card-header">
        <span className="pb-admin-kb-card-icon" aria-hidden="true">
          <CollectionIcon icon={collection.icon} size={19} />
        </span>
        <span className="pb-admin-kb-card-title">{collection.name}</span>
        <ChevronRight className="text-fg-4" size={18} />
      </div>
      <p className="pb-admin-kb-card-copy">{collection.blurb}</p>
      <div className="pb-admin-kb-card-footer">
        <span className="pb-admin-kb-count">
          {collection.documents.length} {collection.documents.length === 1 ? 'document' : 'documents'}
        </span>
        <span className="text-fg-4">·</span>
        <CollectionStatus collection={collection} />
      </div>
    </button>
  )
}

function CollectionStatus({ collection }: { collection: KBCollectionViewModel }) {
  if (collection.failedCount > 0) {
    return (
      <span className="pb-admin-kb-danger">
        <AlertTriangle size={13} />
        {collection.failedCount} {collection.failedCount === 1 ? 'needs' : 'need'} attention
      </span>
    )
  }
  if (collection.processingCount > 0) {
    return (
      <span className="pb-admin-kb-info">
        <LoaderCircle className="pb-spin" size={13} />
        {collection.processingCount} processing
      </span>
    )
  }
  return <span className="pb-admin-kb-muted">{collection.documents.length === 0 ? 'No documents yet' : 'All ready'}</span>
}

interface CollectionDetailProps {
  canManage: boolean
  collection: KBCollectionViewModel
  onBack: () => void
  onDelete: (id: string) => void
  onEdit: (id: string) => void
  onRetry: (id: string) => void
  onToggleOfficial: (id: string, isOfficial: boolean) => void
  onUpload: (request: UploadKBDocumentRequest) => Promise<KBDocument>
}

type LocalUploadPhase = 'requesting' | 'uploading' | 'queued' | 'failed'

interface LocalUploadRow {
  errorMessage?: string
  file: File
  id: string
  percent: number
  phase: LocalUploadPhase
}

function CollectionDetail({
  canManage,
  collection,
  onBack,
  onDelete,
  onEdit,
  onRetry,
  onToggleOfficial,
  onUpload,
}: CollectionDetailProps) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [localUploads, setLocalUploads] = useState<LocalUploadRow[]>([])
  const subtitle = `${collection.documents.length} ${collection.documents.length === 1 ? 'document' : 'documents'} · grounds athlete answers`

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
          <CollectionIcon icon={collection.icon} size={17} />
        </span>
        <span>{collection.blurb}</span>
      </div>
      {localUploads.length > 0 && (
        <div className="pb-admin-kb-doc-list mb-3">
          {localUploads.map((upload) => (
            <LocalUploadRowView
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
              onToggleOfficial={() => onToggleOfficial(document.id, !document.is_official)}
            />
          ))}
        </div>
      )}
    </AdminPageScaffold>
  )
}

function LocalUploadRowView({
  onRetry,
  upload,
}: {
  onRetry: () => void
  upload: LocalUploadRow
}) {
  const failed = upload.phase === 'failed'
  return (
    <article className="pb-admin-kb-doc-row" data-failed={failed}>
      <div className="pb-admin-kb-doc-main">
        <span className="pb-admin-kb-file-icon" aria-hidden="true">
          <FileText size={17} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="pb-admin-kb-doc-title">{upload.file.name}</span>
          </div>
          <p className="pb-admin-kb-doc-meta">{formatBytes(upload.file.size)} · Direct upload</p>
        </div>
        <span className={failed ? 'pb-admin-kb-status text-danger' : 'pb-admin-kb-status text-info'}>
          {failed ? <AlertTriangle size={14} /> : <LoaderCircle className="pb-spin" size={14} />}
          {formatLocalUploadPhase(upload)}
        </span>
      </div>
      {upload.phase === 'uploading' && (
        <div className="px-3 pb-3">
          <div className="h-1.5 overflow-hidden rounded-pill bg-surface-hover" aria-hidden="true">
            <span
              className="block h-full rounded-pill bg-brand"
              style={{ width: `${upload.percent}%` }}
            />
          </div>
          <p className="pb-ui-xs mt-1 text-fg-3" role="status">
            Uploading {upload.percent}%
          </p>
        </div>
      )}
      {failed && (
        <div className="pb-admin-kb-failure">
          <AlertTriangle className="shrink-0 text-danger" size={14} />
          <span className="flex-1">{upload.errorMessage ?? 'Upload failed.'}</span>
          <button className="pb-admin-kb-inline-action" onClick={onRetry} type="button">
            <RefreshCw size={13} />
            Try again
          </button>
        </div>
      )}
    </article>
  )
}

function formatLocalUploadPhase(upload: LocalUploadRow): string {
  if (upload.phase === 'requesting') return 'Preparing'
  if (upload.phase === 'uploading') return `Uploading ${upload.percent}%`
  if (upload.phase === 'queued') return 'Queued'
  return 'Failed'
}

function getSafeUploadErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message) return error.message
  return 'Upload failed before Playbook received it.'
}

function formatBytes(sizeBytes: number): string {
  if (!Number.isFinite(sizeBytes) || sizeBytes <= 0) return 'Unknown size'
  if (sizeBytes >= 1_000_000) return `${(sizeBytes / 1_000_000).toFixed(1)} MB`
  return `${Math.max(1, Math.round(sizeBytes / 1_000))} KB`
}

function CollectionIcon({ icon, size }: { icon: KBCollectionIcon; size: number }) {
  const icons = {
    'book-open': BookOpen,
    database: Database,
    plane: Plane,
    shield: Shield,
    users: Users,
  }
  const Icon = icons[icon]
  return <Icon size={size} />
}
