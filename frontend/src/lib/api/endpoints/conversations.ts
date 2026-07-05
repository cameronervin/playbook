import { apiClient } from '@/src/lib/api/client'
import { postDirectUpload } from '@/src/lib/api/directUpload'
import { validateUploadFile } from '@/src/lib/api/uploadValidation'
import { API_URL, API_VERSION } from '@/src/lib/constants/config'
import type {
  ConversationCreateRequest,
  ConversationDetail,
  ConversationFileSummary,
  ConversationFileUploadIntentRequest,
  ConversationFileUploadIntentResponse,
  ConversationStartResponse,
  ConversationSummary,
  MessageSubmitRequest,
  MessageSubmitResponse,
  UploadConversationFileRequest,
} from '@/src/types/conversations'

const BASE_PATH = `/api/${API_VERSION}/conversations`

export const listConversations = (): Promise<ConversationSummary[]> =>
  apiClient<ConversationSummary[]>(BASE_PATH)

export const createConversation = (
  request: ConversationCreateRequest,
): Promise<ConversationStartResponse> =>
  apiClient<ConversationStartResponse>(BASE_PATH, {
    method: 'POST',
    json: request,
  })

export const getConversation = (conversationId: string): Promise<ConversationDetail> =>
  apiClient<ConversationDetail>(`${BASE_PATH}/${conversationId}`)

export const submitConversationMessage = ({
  conversationId,
  content,
  file_ids = [],
}: MessageSubmitRequest): Promise<MessageSubmitResponse> =>
  apiClient<MessageSubmitResponse>(`${BASE_PATH}/${conversationId}/messages`, {
    method: 'POST',
    json: {
      content,
      file_ids,
    },
  })

export const createConversationMessageStream = (streamUrl: string): EventSource =>
  new EventSource(toApiUrl(streamUrl), { withCredentials: true })

export const createConversationFileUploadIntent = (
  conversationId: string,
  request: ConversationFileUploadIntentRequest,
): Promise<ConversationFileUploadIntentResponse> =>
  apiClient<ConversationFileUploadIntentResponse>(`${BASE_PATH}/${conversationId}/files`, {
    method: 'POST',
    json: {
      filename: request.filename,
      content_type: request.content_type,
      size_bytes: request.size_bytes,
      message_id: request.message_id ?? null,
    },
  })

export const completeConversationFileUpload = (
  conversationId: string,
  fileId: string,
  uploadRequestId: string,
): Promise<ConversationFileSummary> =>
  apiClient<ConversationFileSummary>(`${BASE_PATH}/${conversationId}/files/${fileId}/upload-complete`, {
    method: 'POST',
    json: { upload_request_id: uploadRequestId },
  })

export const uploadConversationFile = async ({
  conversationId,
  file,
  message_id,
  onProgress,
}: UploadConversationFileRequest): Promise<ConversationFileSummary> => {
  const validatedFile = validateUploadFile(file)
  const intent = await createConversationFileUploadIntent(conversationId, {
    filename: validatedFile.filename,
    content_type: validatedFile.contentType,
    size_bytes: validatedFile.sizeBytes,
    message_id: message_id ?? null,
  })
  await postDirectUpload({
    contract: intent.upload,
    file,
    onProgress,
  })
  return completeConversationFileUpload(
    conversationId,
    intent.file.id,
    intent.upload.upload_request_id,
  )
}

function toApiUrl(pathOrUrl: string): string {
  if (/^https?:\/\//i.test(pathOrUrl)) return pathOrUrl
  return `${API_URL}${pathOrUrl}`
}
