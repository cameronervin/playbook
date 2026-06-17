import { apiClient } from '@/src/lib/api/client'
import { postDirectUpload } from '@/src/lib/api/directUpload'
import { validateUploadFile } from '@/src/lib/api/uploadValidation'
import { API_VERSION } from '@/src/lib/constants/config'
import type {
  KBDocument,
  KBDocumentMetadataUpdateRequest,
  KBDocumentUploadIntentRequest,
  KBDocumentUploadIntentResponse,
  UploadKBDocumentRequest,
} from '@/src/types/kb'

const BASE_PATH = `/api/${API_VERSION}/admin/kb/documents`

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
      ...(request.title ? { title: request.title } : {}),
      ...(request.metadata_tags ? { metadata_tags: request.metadata_tags } : {}),
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
    title: request.title,
    metadata_tags: request.metadata_tags,
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
