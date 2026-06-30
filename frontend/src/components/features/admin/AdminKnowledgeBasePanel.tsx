'use client'

import { useMemo, useState } from 'react'
import { AdminKBCollectionCreateDialog } from '@/src/components/features/admin/AdminKBCollectionCreateDialog'
import { AdminKBCollectionDetail } from '@/src/components/features/admin/AdminKBCollectionDetail'
import { AdminKBCollectionGrid } from '@/src/components/features/admin/AdminKBCollectionGrid'
import { AdminKBManageTagsDialog } from '@/src/components/features/admin/AdminKBManageTagsDialog'
import { AdminKBMetadataDrawer } from '@/src/components/features/admin/AdminKBMetadataDrawer'
import { buildKBCollectionViews } from '@/src/lib/fixtures/kbCollections'
import type {
  KBCollection,
  KBCollectionCreateRequest,
  KBDocument,
  KBDocumentMetadataUpdateRequest,
  KBMetadataTag,
  KBMetadataTagCreateRequest,
  KBMetadataTagUpdateRequest,
  UploadKBDocumentRequest,
} from '@/src/types/kb'

interface AdminKnowledgeBasePanelProps {
  canCreateCollection: boolean
  canManageDocuments: boolean
  canManageTags: boolean
  collections: KBCollection[]
  documents: KBDocument[]
  isError?: boolean
  isFetching?: boolean
  isLoading?: boolean
  metadataTags: KBMetadataTag[]
  onArchiveMetadataTag: (tagId: string) => Promise<unknown>
  onCreateCollection: (request: KBCollectionCreateRequest) => Promise<KBCollection>
  onCreateMetadataTag: (request: KBMetadataTagCreateRequest) => Promise<unknown>
  onDelete: (id: string) => void
  onRetry: (id: string) => void
  onUpdateMetadata: (documentId: string, metadata: KBDocumentMetadataUpdateRequest) => Promise<KBDocument>
  onUpdateMetadataTag: (tagId: string, request: KBMetadataTagUpdateRequest) => Promise<unknown>
  onUpload: (request: UploadKBDocumentRequest) => Promise<KBDocument>
}

export function AdminKnowledgeBasePanel({
  canCreateCollection,
  canManageDocuments,
  canManageTags,
  collections,
  documents,
  isError = false,
  isFetching = false,
  isLoading = false,
  metadataTags,
  onArchiveMetadataTag,
  onCreateCollection,
  onCreateMetadataTag,
  onDelete,
  onRetry,
  onUpdateMetadata,
  onUpdateMetadataTag,
  onUpload,
}: AdminKnowledgeBasePanelProps) {
  const [openId, setOpenId] = useState<string | null>(null)
  const [editingDocumentId, setEditingDocumentId] = useState<string | null>(null)
  const [createCollectionOpen, setCreateCollectionOpen] = useState(false)
  const [manageTagsOpen, setManageTagsOpen] = useState(false)
  const collectionViews = useMemo(() => buildKBCollectionViews(documents, collections), [collections, documents])
  const openCollection = openId ? collectionViews.find((collection) => collection.id === openId) : null
  const editingDocument = editingDocumentId ? documents.find((document) => document.id === editingDocumentId) ?? null : null

  const handleCreateCollection = async (request: KBCollectionCreateRequest) => {
    const collection = await onCreateCollection(request)
    setOpenId(collection.id)
    return collection
  }

  if (openCollection) {
    return (
      <>
        <AdminKBCollectionDetail
          canManage={canManageDocuments}
          canManageTags={canManageTags}
          collection={openCollection}
          metadataTags={metadataTags}
          onBack={() => setOpenId(null)}
          onDelete={onDelete}
          onEdit={setEditingDocumentId}
          onManageTags={() => setManageTagsOpen(true)}
          onRetry={onRetry}
          onUpload={onUpload}
        />
        <AdminKBMetadataDrawer
          canManage={canManageDocuments}
          document={editingDocument}
          metadataTags={metadataTags}
          onClose={() => setEditingDocumentId(null)}
          onDelete={onDelete}
          onSave={onUpdateMetadata}
        />
        <AdminKBManageTagsDialog
          onArchive={onArchiveMetadataTag}
          onCreate={onCreateMetadataTag}
          onOpenChange={setManageTagsOpen}
          onUpdate={onUpdateMetadataTag}
          open={manageTagsOpen}
          tags={metadataTags}
        />
      </>
    )
  }

  return (
    <>
      <AdminKBCollectionGrid
        canCreateCollection={canCreateCollection}
        canManageTags={canManageTags}
        collections={collectionViews}
        isError={isError}
        isFetching={isFetching}
        isLoading={isLoading}
        onCreateCollection={() => setCreateCollectionOpen(true)}
        onManageTags={() => setManageTagsOpen(true)}
        onOpen={setOpenId}
      />
      <AdminKBCollectionCreateDialog
        onCreate={handleCreateCollection}
        onOpenChange={setCreateCollectionOpen}
        open={createCollectionOpen}
      />
      <AdminKBManageTagsDialog
        onArchive={onArchiveMetadataTag}
        onCreate={onCreateMetadataTag}
        onOpenChange={setManageTagsOpen}
        onUpdate={onUpdateMetadataTag}
        open={manageTagsOpen}
        tags={metadataTags}
      />
    </>
  )
}
