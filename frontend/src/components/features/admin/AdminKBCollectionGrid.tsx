import { AlertTriangle, ChevronRight, LoaderCircle, Lock, Plus } from 'lucide-react'
import { AdminPageScaffold } from '@/src/components/features/admin/AdminPageScaffold'
import { COLLECTION_ICON_COMPONENTS } from '@/src/components/features/admin/kbFormatting'
import { AdminKBSkeleton } from '@/src/components/features/loading/PlaybookLoaders'
import { Button } from '@/src/components/ui'
import type { KBCollectionViewModel } from '@/src/types/kb'

interface AdminKBCollectionGridProps {
  canManage: boolean
  collections: KBCollectionViewModel[]
  isError: boolean
  isFetching: boolean
  isLoading: boolean
  onCreateCollection: () => void
  onOpen: (id: string) => void
}

export function AdminKBCollectionGrid({
  canManage,
  collections,
  isError,
  isFetching,
  isLoading,
  onCreateCollection,
  onOpen,
}: AdminKBCollectionGridProps) {
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
            <p className="pb-admin-table-text mb-3 rounded-md border border-danger/30 bg-danger-bg px-3 py-2 text-danger">
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
  const Icon = COLLECTION_ICON_COMPONENTS[collection.icon]

  return (
    <button
      className="pb-admin-kb-card"
      onClick={onOpen}
      type="button"
      aria-label={`${collection.name} collection`}
    >
      <div className="pb-admin-kb-card-header">
        <span className="pb-admin-kb-card-icon" aria-hidden="true">
          <Icon size={19} />
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
