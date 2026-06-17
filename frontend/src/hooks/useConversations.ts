import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createConversation,
  getConversation,
  listConversations,
  uploadConversationFile,
} from '@/src/lib/api/endpoints/conversations'
import { QUERY_KEYS } from '@/src/lib/constants/config'
import type { ConversationDetail } from '@/src/types/conversations'

const CONVERSATION_FILE_STATUS_REFETCH_INTERVAL_MS = 3_000

export const useConversations = () =>
  useQuery({
    queryKey: [QUERY_KEYS.conversations],
    queryFn: listConversations,
  })

export const useConversationDetail = (conversationId: string | null) =>
  useQuery({
    queryKey: [QUERY_KEYS.conversationDetail, conversationId],
    queryFn: () => getConversation(conversationId ?? ''),
    enabled: Boolean(conversationId),
    refetchInterval: (query) => {
      const conversation = query.state.data as ConversationDetail | undefined
      return hasActiveConversationFileStatus(conversation)
        ? CONVERSATION_FILE_STATUS_REFETCH_INTERVAL_MS
        : false
    },
  })

export const useCreateConversation = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: createConversation,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.conversations] })
    },
  })
}

export const useUploadConversationFile = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: uploadConversationFile,
    onSettled: async (_data, _error, variables) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.conversations] }),
        queryClient.invalidateQueries({
          queryKey: [QUERY_KEYS.conversationDetail, variables.conversationId],
        }),
      ])
    },
  })
}

function hasActiveConversationFileStatus(conversation: ConversationDetail | undefined): boolean {
  return Boolean(
    conversation?.files.some((file) =>
      ['upload_pending', 'uploaded', 'extracting'].includes(file.extraction_status),
    ),
  )
}
