import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  deleteKBDocument,
  listKBDocuments,
  retryKBDocument,
  updateKBDocumentMetadata,
  uploadKBDocument,
} from '@/src/lib/api/endpoints/kbDocuments'
import { QUERY_KEYS } from '@/src/lib/constants/config'
import type { KBDocument, KBDocumentMetadataUpdateRequest } from '@/src/types/kb'

const KB_DOCUMENT_STATUS_REFETCH_INTERVAL_MS = 3_000

export const useKBDocuments = () =>
  useQuery({
    queryKey: [QUERY_KEYS.kbDocuments],
    queryFn: listKBDocuments,
    refetchInterval: (query) => {
      const documents = query.state.data as KBDocument[] | undefined
      return hasActiveKBDocumentStatus(documents) ? KB_DOCUMENT_STATUS_REFETCH_INTERVAL_MS : false
    },
  })

export const useUploadKBDocument = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: uploadKBDocument,
    onSettled: () => queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.kbDocuments] }),
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
      metadata,
    }: {
      documentId: string
      metadata: KBDocumentMetadataUpdateRequest
    }) => updateKBDocumentMetadata(documentId, metadata),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.kbDocuments] }),
  })
}

function hasActiveKBDocumentStatus(documents: KBDocument[] | undefined): boolean {
  return Boolean(
    documents?.some((document) =>
      ['upload_pending', 'uploaded', 'processing'].includes(document.processing_status),
    ),
  )
}
