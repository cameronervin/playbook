import * as DropdownMenuPrimitive from '@radix-ui/react-dropdown-menu'
import { AlertTriangle, LoaderCircle, MoreHorizontal, Plus, Tags, Trash2 } from 'lucide-react'
import { AdminPageScaffold } from '@/src/components/features/admin/AdminPageScaffold'
import { COLLECTION_ICON_COMPONENTS } from '@/src/components/features/admin/kbFormatting'
import { AdminKBSkeleton } from '@/src/components/features/loading/PlaybookLoaders'
import { Button, Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/src/components/ui'
import { cn } from '@/src/lib/utils/cn'
import type { KBCollectionViewModel } from '@/src/types/kb'

interface AdminKBCollectionGridProps {
  canCreateCollection: boolean
  canDeleteCollection: boolean
  canManageTags: boolean
  collections: KBCollectionViewModel[]
  isError: boolean
  isFetching: boolean
  isLoading: boolean
  onCreateCollection: () => void
  onDeleteCollection: (collection: KBCollectionViewModel) => void
  onManageTags: () => void
  onOpen: (id: string) => void
}

export function AdminKBCollectionGrid({
  canCreateCollection,
  canDeleteCollection,
  canManageTags,
  collections,
  isError,
  isFetching,
  isLoading,
  onCreateCollection,
  onDeleteCollection,
  onManageTags,
  onOpen,
}: AdminKBCollectionGridProps) {
  const totalDocuments = collections.reduce((count, collection) => count + collection.documents.length, 0)

  return (
    <AdminPageScaffold
      actions={
        canManageTags || canCreateCollection ? (
          <>
          {canManageTags && (
            <Button className="pb-admin-header-control" onClick={onManageTags} size="sm" variant="secondary">
              <Tags size={15} />
              Manage tags
            </Button>
          )}
          {canCreateCollection && (
            <Button className="pb-admin-header-control" onClick={onCreateCollection} size="sm" variant="secondary">
              <Plus size={15} />
              New collection
            </Button>
          )}
          </>
        ) : null
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
              <CollectionCard
                canDeleteCollection={canDeleteCollection}
                collection={collection}
                key={collection.id}
                onDeleteCollection={() => onDeleteCollection(collection)}
                onOpen={() => onOpen(collection.id)}
              />
            ))}
          </div>
        </>
      )}
    </AdminPageScaffold>
  )
}

interface CollectionCardProps {
  canDeleteCollection: boolean
  collection: KBCollectionViewModel
  onDeleteCollection: () => void
  onOpen: () => void
}

function CollectionCard({
  canDeleteCollection,
  collection,
  onDeleteCollection,
  onOpen,
}: CollectionCardProps) {
  const Icon = COLLECTION_ICON_COMPONENTS[collection.icon]

  return (
    <article
      className="pb-admin-kb-card"
    >
      <button
        className="pb-admin-kb-card-open"
        onClick={onOpen}
        type="button"
        aria-label={`${collection.title} collection`}
      >
        <div className="pb-admin-kb-card-header">
          <span className="pb-admin-kb-card-icon" aria-hidden="true">
            <Icon size={19} />
          </span>
          <span className="pb-admin-kb-card-title">{collection.title}</span>
        </div>
        <p className="pb-admin-kb-card-copy">{collection.description}</p>
        <div className="pb-admin-kb-card-footer">
          <span className="pb-admin-kb-count">
            {collection.documents.length} {collection.documents.length === 1 ? 'document' : 'documents'}
          </span>
          <span className="text-fg-4">·</span>
          <CollectionStatus collection={collection} />
        </div>
      </button>
      {canDeleteCollection && (
        <CollectionActions
          collection={collection}
          onDeleteCollection={onDeleteCollection}
        />
      )}
    </article>
  )
}

interface CollectionActionsProps {
  collection: KBCollectionViewModel
  onDeleteCollection: () => void
}

function CollectionActions({ collection, onDeleteCollection }: CollectionActionsProps) {
  const hasDocuments = collection.documents.length > 0

  return (
    <DropdownMenuPrimitive.Root>
      <DropdownMenuPrimitive.Trigger asChild>
        <button
          aria-label={`Collection actions for ${collection.title}`}
          className="pb-admin-kb-card-action"
          type="button"
        >
          <MoreHorizontal size={18} />
        </button>
      </DropdownMenuPrimitive.Trigger>
      <DropdownMenuPrimitive.Portal>
        <DropdownMenuPrimitive.Content align="end" className="pb-admin-menu" sideOffset={4}>
          <TooltipProvider delayDuration={150}>
            <Tooltip>
              <TooltipTrigger asChild>
                <DropdownMenuPrimitive.Item
                  aria-disabled={hasDocuments}
                  className={cn('pb-admin-menu-item pb-focus-item text-danger', hasDocuments && 'text-fg-4')}
                  data-disabled={hasDocuments ? '' : undefined}
                  onSelect={(event) => {
                    if (hasDocuments) {
                      event.preventDefault()
                      return
                    }
                    onDeleteCollection()
                  }}
                >
                  <Trash2 className={hasDocuments ? 'text-fg-4' : 'text-danger'} size={16} />
                  Delete collection
                </DropdownMenuPrimitive.Item>
              </TooltipTrigger>
              {hasDocuments && (
                <TooltipContent side="left">
                  Delete the documents in this collection first.
                </TooltipContent>
              )}
            </Tooltip>
          </TooltipProvider>
        </DropdownMenuPrimitive.Content>
      </DropdownMenuPrimitive.Portal>
    </DropdownMenuPrimitive.Root>
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
