import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createConversation,
  getConversation,
  listConversations,
} from '@/src/lib/api/endpoints/conversations'
import { QUERY_KEYS } from '@/src/lib/constants/config'

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
