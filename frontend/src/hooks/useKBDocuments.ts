import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  deleteKBDocument,
  listKBDocuments,
  retryKBDocument,
  updateKBDocumentMetadata,
  uploadKBDocument,
} from '@/src/lib/api/endpoints/kbDocuments'
import { QUERY_KEYS } from '@/src/lib/constants/config'
import type { KBDocumentMetadataUpdateRequest } from '@/src/types/kb'

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
    mutationFn: ({
      documentId,
      isOfficial,
      metadata,
    }: {
      documentId: string
      isOfficial?: boolean
      metadata?: KBDocumentMetadataUpdateRequest
    }) =>
      updateKBDocumentMetadata(documentId, {
        ...metadata,
        ...(typeof isOfficial === 'boolean' ? { is_official: isOfficial } : {}),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.kbDocuments] }),
  })
}
