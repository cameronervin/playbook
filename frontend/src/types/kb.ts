import type { DirectUploadContract, DirectUploadMutationOptions } from '@/src/types/uploads'

export type KBDocumentStatus = 'upload_pending' | 'uploaded' | 'processing' | 'ready' | 'failed'

export interface KBDocument {
  id: string
  organization_id: string
  uploaded_by: string
  title: string
  filename: string
  content_type: string
  size_bytes: number
  processing_status: KBDocumentStatus
  failure_reason: string | null
  collection_id: string | null
  tag_slugs: string[]
  visibility_policy: Record<string, unknown>
  metadata_tags: Record<string, unknown>
  source_date: string | null
  kb_service_document_id: string | null
  created_at: string
  updated_at: string
}

export interface KBDocumentMetadataUpdateRequest {
  tag_slugs?: string[]
  source_date?: string | null
}

export interface KBDocumentUploadIntentRequest {
  filename: string
  content_type: string
  size_bytes: number
  collection_id: string
  tag_slugs?: string[]
  title?: string
  source_date?: string | null
}

export interface KBDocumentUploadIntentResponse {
  document: KBDocument
  upload: DirectUploadContract
}

export interface UploadKBDocumentRequest extends DirectUploadMutationOptions {
  file: File
  collection_id: string
  tag_slugs?: string[]
  title?: string
  source_date?: string | null
}

export type KBCollectionIcon = 'shield' | 'plane' | 'book-open' | 'users' | 'database'

export interface KBCollection {
  id: string
  organization_id: string
  slug: string
  title: string
  description: string
  icon: KBCollectionIcon
  sort_order: number
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface KBCollectionCreateRequest {
  title: string
  description: string
  icon: KBCollectionIcon
}

export interface KBMetadataTag {
  id: string
  organization_id: string
  slug: string
  label: string
  sort_order: number
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface KBMetadataTagCreateRequest {
  label: string
}

export interface KBMetadataTagUpdateRequest {
  label: string
}

export interface KBCollectionViewModel extends KBCollection {
  documents: KBDocument[]
  failedCount: number
  processingCount: number
}
