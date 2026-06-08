import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  deleteKBDocument,
  listKBDocuments,
  retryKBDocument,
  updateKBDocumentMetadata,
  uploadKBDocument,
} from '@/src/lib/api/endpoints/kbDocuments'
import { QUERY_KEYS } from '@/src/lib/constants/config'

export const useKBDocuments = () =>
  useQuery({
    queryKey: [QUERY_KEYS.kbDocuments],
    queryFn: listKBDocuments,
  })

export const useUploadKBDocument = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: uploadKBDocument,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.kbDocuments] }),
  })
}

export const useRetryKBDocument = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: retryKBDocument,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.kbDocuments] }),
  })
}

export const useDeleteKBDocument = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteKBDocument,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.kbDocuments] }),
  })
}

export const useUpdateKBDocumentMetadata = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ documentId, isOfficial }: { documentId: string; isOfficial: boolean }) =>
      updateKBDocumentMetadata(documentId, { is_official: isOfficial }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.kbDocuments] }),
  })
}
