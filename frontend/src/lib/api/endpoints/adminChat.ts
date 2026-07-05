import { apiClient } from '@/src/lib/api/client'
import { API_URL, API_VERSION } from '@/src/lib/constants/config'
import type {
  AdminChatMessageSubmitPayload,
  AdminChatMessageSubmitRequest,
  AdminChatMessageSubmitResponse,
  AdminChatSession,
  AdminChatSessionCreateRequest,
  AdminChatSessionDetail,
} from '@/src/types/adminChat'

const ADMIN_CHAT_SESSIONS_PATH = `/api/${API_VERSION}/admin/chat/sessions`

export const listAdminChatSessions = (): Promise<AdminChatSession[]> =>
  apiClient<AdminChatSession[]>(ADMIN_CHAT_SESSIONS_PATH)

export const createAdminChatSession = (
  request: AdminChatSessionCreateRequest = {},
): Promise<AdminChatSession> =>
  apiClient<AdminChatSession>(ADMIN_CHAT_SESSIONS_PATH, {
    method: 'POST',
    json: request,
  })

export const getAdminChatSession = (
  sessionId: string,
): Promise<AdminChatSessionDetail> =>
  apiClient<AdminChatSessionDetail>(`${ADMIN_CHAT_SESSIONS_PATH}/${sessionId}`)

export const submitAdminChatMessage = ({
  sessionId,
  question,
  window,
  window_start,
  window_end,
}: AdminChatMessageSubmitRequest): Promise<AdminChatMessageSubmitResponse> => {
  const payload: AdminChatMessageSubmitPayload = { question }
  if (window) payload.window = window
  if (window_start !== undefined) payload.window_start = window_start
  if (window_end !== undefined) payload.window_end = window_end

  return apiClient<AdminChatMessageSubmitResponse>(
    `${ADMIN_CHAT_SESSIONS_PATH}/${sessionId}/messages`,
    {
      method: 'POST',
      json: payload,
    },
  )
}

export const createAdminChatMessageStream = (streamUrl: string): EventSource =>
  new EventSource(toApiUrl(streamUrl), { withCredentials: true })

function toApiUrl(pathOrUrl: string): string {
  if (/^https?:\/\//i.test(pathOrUrl)) return pathOrUrl
  return `${API_URL}${pathOrUrl}`
}
