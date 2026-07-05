'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AUTH_EXPIRED_EVENT, isAuthExpiredError } from '@/src/lib/api/client'
import { ROUTES } from '@/src/lib/constants/config'
import { useUIStore } from '@/src/lib/store/uiStore'

interface ProvidersProps {
  children: React.ReactNode
}

export function Providers({ children }: ProvidersProps) {
  const router = useRouter()
  // useState keeps a single QueryClient instance stable across re-renders.
  const [queryClient] = useState(
    () => {
      const clientRef: { current: QueryClient | null } = { current: null }
      const handleAuthExpired = () => {
        useUIStore.getState().resetSessionState()
        const client = clientRef.current
        if (!client) return
        client.clear()
        router.replace(`${ROUTES.login}?reason=session_expired`)
      }

      const client = new QueryClient({
        mutationCache: new MutationCache({
          onError: (error) => {
            if (isAuthExpiredError(error)) handleAuthExpired()
          },
        }),
        queryCache: new QueryCache({
          onError: (error) => {
            if (isAuthExpiredError(error)) handleAuthExpired()
          },
        }),
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000,
            refetchOnWindowFocus: false,
          },
        },
      })
      clientRef.current = client
      return client
    },
  )

  useEffect(() => {
    const handleAuthExpired = () => {
      useUIStore.getState().resetSessionState()
      queryClient.clear()
      router.replace(`${ROUTES.login}?reason=session_expired`)
    }
    window.addEventListener(AUTH_EXPIRED_EVENT, handleAuthExpired)
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, handleAuthExpired)
  }, [queryClient, router])

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}
