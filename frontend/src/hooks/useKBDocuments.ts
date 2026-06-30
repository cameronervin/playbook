import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  archiveKBMetadataTag,
  createKBCollection,
  createKBMetadataTag,
  deleteKBDocument,
  listKBCollections,
  listKBDocuments,
  listKBMetadataTags,
  retryKBDocument,
  updateKBMetadataTag,
  updateKBDocumentMetadata,
  uploadKBDocument,
} from '@/src/lib/api/endpoints/kbDocuments'
import { QUERY_KEYS } from '@/src/lib/constants/config'
import type {
  KBCollection,
  KBCollectionCreateRequest,
  KBDocument,
  KBMetadataTag,
  KBMetadataTagCreateRequest,
  KBMetadataTagUpdateRequest,
  KBDocumentMetadataUpdateRequest,
} from '@/src/types/kb'

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

export const useKBCollections = () =>
  useQuery({
    queryKey: [QUERY_KEYS.kbCollections],
    queryFn: listKBCollections,
  })

export const useKBMetadataTags = () =>
  useQuery({
    queryKey: [QUERY_KEYS.kbMetadataTags],
    queryFn: () => listKBMetadataTags(true),
  })

export const useCreateKBCollection = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (request: KBCollectionCreateRequest) => createKBCollection(request),
    onSuccess: (collection) => {
      queryClient.setQueryData<KBCollection[]>([QUERY_KEYS.kbCollections], (current) =>
        current ? [...current.filter((item) => item.id !== collection.id), collection] : [collection],
      )
      queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.kbCollections] })
    },
  })
}

export const useCreateKBMetadataTag = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (request: KBMetadataTagCreateRequest) => createKBMetadataTag(request),
    onSuccess: (tag) => {
      queryClient.setQueryData<KBMetadataTag[]>([QUERY_KEYS.kbMetadataTags], (current) =>
        current ? [...current.filter((item) => item.id !== tag.id), tag] : [tag],
      )
      queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.kbMetadataTags] })
    },
  })
}

export const useUpdateKBMetadataTag = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      tagId,
      request,
    }: {
      tagId: string
      request: KBMetadataTagUpdateRequest
    }) => updateKBMetadataTag(tagId, request),
    onSuccess: (tag) => {
      queryClient.setQueryData<KBMetadataTag[]>([QUERY_KEYS.kbMetadataTags], (current) =>
        current?.map((item) => (item.id === tag.id ? tag : item)) ?? [tag],
      )
      queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.kbMetadataTags] })
    },
  })
}

export const useArchiveKBMetadataTag = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: archiveKBMetadataTag,
    onSuccess: (_, tagId) => {
      queryClient.setQueryData<KBMetadataTag[]>([QUERY_KEYS.kbMetadataTags], (current) =>
        current?.map((item) => (item.id === tagId ? { ...item, is_active: false } : item)),
      )
      queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.kbMetadataTags] })
    },
  })
}

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
