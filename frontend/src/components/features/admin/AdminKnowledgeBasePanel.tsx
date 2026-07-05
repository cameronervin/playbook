'use client'

import { useMemo, useState } from 'react'
import { AdminKBCollectionCreateDialog } from '@/src/components/features/admin/AdminKBCollectionCreateDialog'
import { AdminKBCollectionDeleteDialog } from '@/src/components/features/admin/AdminKBCollectionDeleteDialog'
import { AdminKBCollectionDetail } from '@/src/components/features/admin/AdminKBCollectionDetail'
import { AdminKBCollectionGrid } from '@/src/components/features/admin/AdminKBCollectionGrid'
import { AdminKBManageTagsDialog } from '@/src/components/features/admin/AdminKBManageTagsDialog'
import { AdminKBMetadataDrawer } from '@/src/components/features/admin/AdminKBMetadataDrawer'
import { buildKBCollectionViews } from '@/src/lib/fixtures/kbCollections'
import type {
  KBCollection,
  KBCollectionCreateRequest,
  KBCollectionViewModel,
  KBDocument,
  KBDocumentMetadataUpdateRequest,
  KBMetadataTag,
  KBMetadataTagCreateRequest,
  KBMetadataTagUpdateRequest,
  UploadKBDocumentRequest,
} from '@/src/types/kb'

interface AdminKnowledgeBasePanelProps {
  canCreateCollection: boolean
  canDeleteCollection: boolean
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
  onDeleteCollection: (collectionId: string) => Promise<unknown>
  onDeleteMetadataTagPermanently: (tagId: string) => Promise<unknown>
  onDelete: (id: string) => void
  onRetry: (id: string) => void
  onUnarchiveMetadataTag: (tagId: string) => Promise<unknown>
  onUpdateMetadata: (documentId: string, metadata: KBDocumentMetadataUpdateRequest) => Promise<KBDocument>
  onUpdateMetadataTag: (tagId: string, request: KBMetadataTagUpdateRequest) => Promise<unknown>
  onUpload: (request: UploadKBDocumentRequest) => Promise<KBDocument>
}

export function AdminKnowledgeBasePanel({
  canCreateCollection,
  canDeleteCollection,
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
  onDeleteCollection,
  onDeleteMetadataTagPermanently,
  onDelete,
  onRetry,
  onUnarchiveMetadataTag,
  onUpdateMetadata,
  onUpdateMetadataTag,
  onUpload,
}: AdminKnowledgeBasePanelProps) {
  const [openId, setOpenId] = useState<string | null>(null)
  const [editingDocumentId, setEditingDocumentId] = useState<string | null>(null)
  const [createCollectionOpen, setCreateCollectionOpen] = useState(false)
  const [deletingCollection, setDeletingCollection] = useState<KBCollectionViewModel | null>(null)
  const [manageTagsOpen, setManageTagsOpen] = useState(false)
  const collectionViews = useMemo(() => buildKBCollectionViews(documents, collections), [collections, documents])
  const metadataTagUsageCounts = useMemo(() => buildMetadataTagUsageCounts(documents), [documents])
  const openCollection = openId ? collectionViews.find((collection) => collection.id === openId) : null
  const editingDocument = editingDocumentId ? documents.find((document) => document.id === editingDocumentId) ?? null : null

  const handleCreateCollection = async (request: KBCollectionCreateRequest) => {
    const collection = await onCreateCollection(request)
    setOpenId(collection.id)
    return collection
  }

  const handleDeletedCollection = (collectionId: string) => {
    if (openId === collectionId) setOpenId(null)
  }

  if (openCollection) {
    return (
      <>
        <AdminKBCollectionDetail
          canDeleteCollection={canDeleteCollection}
          canManage={canManageDocuments}
          canManageTags={canManageTags}
          collection={openCollection}
          metadataTags={metadataTags}
          onBack={() => setOpenId(null)}
          onDeleteCollection={setDeletingCollection}
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
          onDeletePermanently={onDeleteMetadataTagPermanently}
          onOpenChange={setManageTagsOpen}
          onUnarchive={onUnarchiveMetadataTag}
          onUpdate={onUpdateMetadataTag}
          open={manageTagsOpen}
          tagUsageCounts={metadataTagUsageCounts}
          tags={metadataTags}
        />
        <AdminKBCollectionDeleteDialog
          collection={deletingCollection}
          onClose={() => setDeletingCollection(null)}
          onDelete={onDeleteCollection}
          onDeleted={handleDeletedCollection}
        />
      </>
    )
  }

  return (
    <>
      <AdminKBCollectionGrid
        canCreateCollection={canCreateCollection}
        canDeleteCollection={canDeleteCollection}
        canManageTags={canManageTags}
        collections={collectionViews}
        isError={isError}
        isFetching={isFetching}
        isLoading={isLoading}
        onCreateCollection={() => setCreateCollectionOpen(true)}
        onDeleteCollection={setDeletingCollection}
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
        onDeletePermanently={onDeleteMetadataTagPermanently}
        onOpenChange={setManageTagsOpen}
        onUnarchive={onUnarchiveMetadataTag}
        onUpdate={onUpdateMetadataTag}
        open={manageTagsOpen}
        tagUsageCounts={metadataTagUsageCounts}
        tags={metadataTags}
      />
      <AdminKBCollectionDeleteDialog
        collection={deletingCollection}
        onClose={() => setDeletingCollection(null)}
        onDelete={onDeleteCollection}
        onDeleted={handleDeletedCollection}
      />
    </>
  )
}

function buildMetadataTagUsageCounts(documents: KBDocument[]): Map<string, number> {
  const counts = new Map<string, number>()
  for (const document of documents) {
    const slugs = new Set([
      ...document.tag_slugs,
      ...readMetadataTagSlugs(document.metadata_tags),
    ])
    for (const slug of slugs) {
      counts.set(slug, (counts.get(slug) ?? 0) + 1)
    }
  }
  return counts
}

function readMetadataTagSlugs(metadataTags: Record<string, unknown>): string[] {
  const value = metadataTags.tag_slugs
  if (!Array.isArray(value)) return []
  return value.filter((item): item is string => typeof item === 'string')
}
