import { apiClient } from '@/src/lib/api/client'
import { API_VERSION } from '@/src/lib/constants/config'
import type {
  ConversationCreateRequest,
  ConversationDetail,
  ConversationSummary,
} from '@/src/types/conversations'

const BASE_PATH = `/api/${API_VERSION}/conversations`

export const listConversations = (): Promise<ConversationSummary[]> =>
  apiClient<ConversationSummary[]>(BASE_PATH)

export const createConversation = (
  request: ConversationCreateRequest,
): Promise<ConversationDetail> =>
  apiClient<ConversationDetail>(BASE_PATH, {
    method: 'POST',
    json: request,
  })

export const getConversation = (conversationId: string): Promise<ConversationDetail> =>
  apiClient<ConversationDetail>(`${BASE_PATH}/${conversationId}`)
