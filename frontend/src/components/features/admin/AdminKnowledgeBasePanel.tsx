'use client'

import { useMemo, useState } from 'react'
import { AdminKBCollectionDetail } from '@/src/components/features/admin/AdminKBCollectionDetail'
import { AdminKBCollectionGrid } from '@/src/components/features/admin/AdminKBCollectionGrid'
import { AdminKBMetadataDrawer } from '@/src/components/features/admin/AdminKBMetadataDrawer'
import { ADMIN_KB_COLLECTIONS, buildKBCollectionViews } from '@/src/lib/fixtures/kbCollections'
import type { UploadKBDocumentRequest } from '@/src/types/kb'
import type { KBCollection, KBDocument, KBDocumentMetadataUpdateRequest } from '@/src/types/kb'

interface AdminKnowledgeBasePanelProps {
  canManage: boolean
  documents: KBDocument[]
  isError?: boolean
  isFetching?: boolean
  isLoading?: boolean
  onDelete: (id: string) => void
  onRetry: (id: string) => void
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
        <AdminKBCollectionDetail
          canManage={canManage}
          collection={openCollection}
          onBack={() => setOpenId(null)}
          onDelete={onDelete}
          onEdit={setEditingDocumentId}
          onRetry={onRetry}
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
    <AdminKBCollectionGrid
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
