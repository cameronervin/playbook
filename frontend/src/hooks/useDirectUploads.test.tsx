import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useUploadConversationFile } from '@/src/hooks/useConversations'
import { useUploadKBDocument } from '@/src/hooks/useKBDocuments'
import { uploadConversationFile } from '@/src/lib/api/endpoints/conversations'
import { uploadKBDocument } from '@/src/lib/api/endpoints/kbDocuments'
import { QUERY_KEYS } from '@/src/lib/constants/config'

vi.mock('@/src/lib/api/endpoints/conversations', () => ({
  uploadConversationFile: vi.fn(),
}))

vi.mock('@/src/lib/api/endpoints/kbDocuments', () => ({
  uploadKBDocument: vi.fn(),
}))

function wrapper(queryClient: QueryClient) {
  return function HookWrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}

describe('direct upload hooks', () => {
  beforeEach(() => {
    vi.mocked(uploadConversationFile).mockReset()
    vi.mocked(uploadKBDocument).mockReset()
  })

  it('invalidates KB document caches after an admin upload settles', async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries')
    vi.mocked(uploadKBDocument).mockResolvedValueOnce({ id: 'doc-1' } as Awaited<ReturnType<typeof uploadKBDocument>>)
    const { result } = renderHook(() => useUploadKBDocument(), { wrapper: wrapper(queryClient) })

    await act(async () => {
      await result.current.mutateAsync({ file: new File(['hello'], 'policy.pdf', { type: 'application/pdf' }) })
    })

    await waitFor(() =>
      expect(invalidate).toHaveBeenCalledWith({ queryKey: [QUERY_KEYS.kbDocuments] }),
    )
  })

  it('invalidates conversation list and detail caches after a conversation file upload settles', async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries')
    vi.mocked(uploadConversationFile).mockResolvedValueOnce({ id: 'file-1' } as Awaited<ReturnType<typeof uploadConversationFile>>)
    const { result } = renderHook(() => useUploadConversationFile(), { wrapper: wrapper(queryClient) })

    await act(async () => {
      await result.current.mutateAsync({
        conversationId: 'conversation-1',
        file: new File(['hello'], 'contract.pdf', { type: 'application/pdf' }),
      })
    })

    await waitFor(() => {
      expect(invalidate).toHaveBeenCalledWith({ queryKey: [QUERY_KEYS.conversations] })
      expect(invalidate).toHaveBeenCalledWith({
        queryKey: [QUERY_KEYS.conversationDetail, 'conversation-1'],
      })
    })
  })
})
