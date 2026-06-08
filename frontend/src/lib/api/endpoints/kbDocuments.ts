import { apiClient } from '@/src/lib/api/client'
import { API_VERSION } from '@/src/lib/constants/config'
import type { KBDocument, KBDocumentMetadataUpdateRequest } from '@/src/types/kb'

const BASE_PATH = `/api/${API_VERSION}/admin/kb/documents`

export interface UploadKBDocumentRequest {
  file: File
  title?: string
  metadata_tags?: Record<string, unknown>
  source_date?: string
  is_official?: boolean
  priority?: number
}

export const listKBDocuments = (): Promise<KBDocument[]> =>
  apiClient<KBDocument[]>(BASE_PATH)

export const uploadKBDocument = (request: UploadKBDocumentRequest): Promise<KBDocument> => {
  const formData = new FormData()
  formData.append('file', request.file)
  if (request.title) formData.append('title', request.title)
  if (request.metadata_tags) formData.append('metadata_tags', JSON.stringify(request.metadata_tags))
  if (request.source_date) formData.append('source_date', request.source_date)
  formData.append('is_official', String(request.is_official ?? false))
  formData.append('priority', String(request.priority ?? 0))
  return apiClient<KBDocument>(BASE_PATH, { method: 'POST', body: formData })
}

export const updateKBDocumentMetadata = (
  documentId: string,
  request: KBDocumentMetadataUpdateRequest,
): Promise<KBDocument> =>
  apiClient<KBDocument>(`${BASE_PATH}/${documentId}/metadata`, {
    method: 'PATCH',
    json: request,
  })

export const retryKBDocument = (documentId: string): Promise<KBDocument> =>
  apiClient<KBDocument>(`${BASE_PATH}/${documentId}/retry`, { method: 'POST' })

export const deleteKBDocument = (documentId: string): Promise<void> =>
  apiClient<void>(`${BASE_PATH}/${documentId}`, { method: 'DELETE' })
