import type { KBCollection, KBCollectionViewModel, KBDocument } from '@/src/types/kb'

export const ADMIN_KB_COLLECTIONS: KBCollection[] = [
  {
    id: 'compliance',
    name: 'Compliance & NIL',
    icon: 'shield',
    blurb: 'NIL, eligibility, and recruiting rules - kept current with department and NCAA policy.',
    keywords: ['nil', 'compliance', 'eligibility', 'recruiting', 'ncaa', 'transfer', 'bylaw'],
  },
  {
    id: 'travel',
    name: 'Team Travel',
    icon: 'plane',
    blurb: 'Per-diem rates, charter logistics, and team hotel policy for every sport.',
    keywords: ['travel', 'per diem', 'per_diem', 'hotel', 'charter', 'team travel'],
  },
  {
    id: 'academics',
    name: 'Academic Services',
    icon: 'book-open',
    blurb: 'Study-hall rules, tutoring, and academic eligibility support.',
    keywords: ['academic', 'academics', 'study', 'tutoring', 'class', 'eligibility support'],
  },
  {
    id: 'donor',
    name: 'Donor Relations',
    icon: 'users',
    blurb: 'Giving levels, suite benefits, and booster club answers for boosters.',
    keywords: ['donor', 'booster', 'cowboy club', 'suite', 'giving'],
  },
]

export function buildKBCollectionViews(
  documents: KBDocument[],
  collections: KBCollection[] = ADMIN_KB_COLLECTIONS,
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

export function collectionUploadMetadata(collection: KBCollection): Record<string, unknown> {
  return {
    collection: collection.id,
    topics: [collection.name],
  }
}

function resolveDocumentCollectionId(document: KBDocument, collections: KBCollection[]): string {
  const metadataCollection = readString(document.metadata_tags.collection)
  if (metadataCollection && hasCollection(metadataCollection, collections)) return metadataCollection

  const searchable = [
    document.title,
    document.filename,
    readString(document.metadata_tags.topic),
    readString(document.metadata_tags.category),
    ...readStringList(document.metadata_tags.topics),
    ...readStringList(document.metadata_tags.tags),
  ]
    .join(' ')
    .toLowerCase()

  return (
    collections.find((collection) =>
      collection.keywords.some((keyword) => searchable.includes(keyword.toLowerCase())),
    )?.id ?? collections[0]?.id ?? ADMIN_KB_COLLECTIONS[0].id
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
