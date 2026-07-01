import { apiClient } from '@/src/lib/api/client'
import { postDirectUpload } from '@/src/lib/api/directUpload'
import { validateUploadFile } from '@/src/lib/api/uploadValidation'
import { API_VERSION } from '@/src/lib/constants/config'
import type {
  KBDocument,
  KBCollection,
  KBCollectionCreateRequest,
  KBMetadataTag,
  KBMetadataTagCreateRequest,
  KBMetadataTagUpdateRequest,
  KBDocumentMetadataUpdateRequest,
  KBDocumentUploadIntentRequest,
  KBDocumentUploadIntentResponse,
  UploadKBDocumentRequest,
} from '@/src/types/kb'

const KB_BASE_PATH = `/api/${API_VERSION}/admin/kb`
const BASE_PATH = `${KB_BASE_PATH}/documents`

export const listKBCollections = (): Promise<KBCollection[]> =>
  apiClient<KBCollection[]>(`${KB_BASE_PATH}/collections`)

export const createKBCollection = (
  request: KBCollectionCreateRequest,
): Promise<KBCollection> =>
  apiClient<KBCollection>(`${KB_BASE_PATH}/collections`, {
    method: 'POST',
    json: request,
  })

export const deleteKBCollection = (collectionId: string): Promise<void> =>
  apiClient<void>(`${KB_BASE_PATH}/collections/${collectionId}`, {
    method: 'DELETE',
  })

export const listKBMetadataTags = (includeArchived = false): Promise<KBMetadataTag[]> =>
  apiClient<KBMetadataTag[]>(
    `${KB_BASE_PATH}/metadata-tags${includeArchived ? '?include_archived=true' : ''}`,
  )

export const createKBMetadataTag = (
  request: KBMetadataTagCreateRequest,
): Promise<KBMetadataTag> =>
  apiClient<KBMetadataTag>(`${KB_BASE_PATH}/metadata-tags`, {
    method: 'POST',
    json: request,
  })

export const updateKBMetadataTag = (
  tagId: string,
  request: KBMetadataTagUpdateRequest,
): Promise<KBMetadataTag> =>
  apiClient<KBMetadataTag>(`${KB_BASE_PATH}/metadata-tags/${tagId}`, {
    method: 'PATCH',
    json: request,
  })

export const archiveKBMetadataTag = (tagId: string): Promise<void> =>
  apiClient<void>(`${KB_BASE_PATH}/metadata-tags/${tagId}`, { method: 'DELETE' })

export const unarchiveKBMetadataTag = (tagId: string): Promise<KBMetadataTag> =>
  apiClient<KBMetadataTag>(`${KB_BASE_PATH}/metadata-tags/${tagId}/unarchive`, {
    method: 'POST',
  })

export const deleteKBMetadataTagPermanently = (tagId: string): Promise<void> =>
  apiClient<void>(`${KB_BASE_PATH}/metadata-tags/${tagId}/permanent`, {
    method: 'DELETE',
  })

export const listKBDocuments = (): Promise<KBDocument[]> =>
  apiClient<KBDocument[]>(BASE_PATH)

export const createKBDocumentUploadIntent = (
  request: KBDocumentUploadIntentRequest,
): Promise<KBDocumentUploadIntentResponse> =>
  apiClient<KBDocumentUploadIntentResponse>(BASE_PATH, {
    method: 'POST',
    json: {
      filename: request.filename,
      content_type: request.content_type,
      size_bytes: request.size_bytes,
      collection_id: request.collection_id,
      ...(request.tag_slugs ? { tag_slugs: request.tag_slugs } : {}),
      ...(request.title ? { title: request.title } : {}),
      ...(request.source_date ? { source_date: request.source_date } : {}),
    },
  })

export const completeKBDocumentUpload = (
  documentId: string,
  uploadRequestId: string,
): Promise<KBDocument> =>
  apiClient<KBDocument>(`${BASE_PATH}/${documentId}/upload-complete`, {
    method: 'POST',
    json: { upload_request_id: uploadRequestId },
  })

export const uploadKBDocument = async (request: UploadKBDocumentRequest): Promise<KBDocument> => {
  const file = validateUploadFile(request.file)
  const intent = await createKBDocumentUploadIntent({
    filename: file.filename,
    content_type: file.contentType,
    size_bytes: file.sizeBytes,
    collection_id: request.collection_id,
    tag_slugs: request.tag_slugs,
    title: request.title,
    source_date: request.source_date,
  })
  await postDirectUpload({
    contract: intent.upload,
    file: request.file,
    onProgress: request.onProgress,
  })
  return completeKBDocumentUpload(intent.document.id, intent.upload.upload_request_id)
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
