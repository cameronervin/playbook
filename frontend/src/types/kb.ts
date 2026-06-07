export type KBDocumentStatus = 'uploaded' | 'processing' | 'ready' | 'failed'

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
  visibility_policy: Record<string, unknown>
  metadata_tags: Record<string, unknown>
  source_date: string | null
  is_official: boolean
  priority: number
  kb_service_document_id: string | null
  created_at: string
  updated_at: string
}

export interface KBDocumentMetadataUpdateRequest {
  metadata_tags?: Record<string, unknown>
  source_date?: string | null
  is_official?: boolean
  priority?: number
}
