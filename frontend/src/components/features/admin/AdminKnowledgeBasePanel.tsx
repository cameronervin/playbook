'use client'

import { useMemo, useRef, useState, type ChangeEvent } from 'react'
import {
  AlertTriangle,
  ArrowLeft,
  BookOpen,
  ChevronRight,
  Database,
  LoaderCircle,
  Lock,
  Plane,
  Plus,
  Shield,
  Upload,
  Users,
} from 'lucide-react'
import { AdminKBDocumentRow } from '@/src/components/features/admin/AdminKBDocumentRow'
import { AdminKBMetadataDrawer } from '@/src/components/features/admin/AdminKBMetadataDrawer'
import { AdminPageScaffold } from '@/src/components/features/admin/AdminPageScaffold'
import { AdminKBSkeleton } from '@/src/components/features/loading/PlaybookLoaders'
import { Button } from '@/src/components/ui'
import { ADMIN_KB_COLLECTIONS, buildKBCollectionViews, collectionUploadMetadata } from '@/src/lib/fixtures/kbCollections'
import type { UploadKBDocumentRequest } from '@/src/lib/api/endpoints/kbDocuments'
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
  onUpload: (request: UploadKBDocumentRequest) => void
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
  onUpload: (request: UploadKBDocumentRequest) => void
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
  const subtitle = `${collection.documents.length} ${collection.documents.length === 1 ? 'document' : 'documents'} · grounds athlete answers`

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    onUpload({
      file,
      metadata_tags: collectionUploadMetadata(collection),
      title: file.name,
    })
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
              <input className="sr-only" onChange={handleFileChange} ref={fileInputRef} type="file" />
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
      {collection.documents.length === 0 ? (
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
