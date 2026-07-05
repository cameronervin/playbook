import type { KBCollection, KBCollectionViewModel, KBDocument } from '@/src/types/kb'

export function buildKBCollectionViews(
  documents: KBDocument[],
  collections: KBCollection[],
): KBCollectionViewModel[] {
  return collections.map((collection) => {
    const collectionDocuments = documents.filter((document) => resolveDocumentCollectionId(document, collections) === collection.id)
    return {
      ...collection,
      documents: collectionDocuments,
      failedCount: collectionDocuments.filter((document) => document.processing_status === 'failed').length,
      processingCount: collectionDocuments.filter((document) => isProcessingDocument(document)).length,
    }
  })
}

function resolveDocumentCollectionId(document: KBDocument, collections: KBCollection[]): string {
  if (document.collection_id && hasCollection(document.collection_id, collections)) return document.collection_id

  const metadataCollection = readString(document.metadata_tags.collection)
  if (metadataCollection) {
    const matched = collections.find((collection) => collection.slug === metadataCollection)
    if (matched) return matched.id
  }

  const searchable = [
    document.title,
    document.filename,
    metadataCollection,
    ...readStringList(document.metadata_tags.topics),
    ...readStringList(document.metadata_tags.tags),
  ]
    .join(' ')
    .toLowerCase()

  return (
    collections.find((collection) =>
      searchable.includes(collection.slug.toLowerCase()) ||
      searchable.includes(collection.title.toLowerCase()),
    )?.id ?? collections[0]?.id ?? ''
  )
}

function isProcessingDocument(document: KBDocument): boolean {
  return (
    document.processing_status === 'upload_pending' ||
    document.processing_status === 'processing' ||
    document.processing_status === 'uploaded'
  )
}

function hasCollection(collectionId: string, collections: KBCollection[]): boolean {
  return collections.some((collection) => collection.id === collectionId)
}

function readString(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null
}

function readStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
}
