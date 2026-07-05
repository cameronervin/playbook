'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { PlaybookRouteLoader } from '@/src/components/features/loading/PlaybookLoaders'
import { useCurrentUser } from '@/src/hooks/useAuth'
import { ROUTES } from '@/src/lib/constants/config'
import { getDefaultAuthenticatedRoute } from '@/src/lib/authRouting'

export default function RootRedirect() {
  const router = useRouter()
  const { data: user, isError, isLoading } = useCurrentUser()

  useEffect(() => {
    if (isLoading) return
    if (isError || !user) {
      router.replace(ROUTES.login)
      return
    }
    router.replace(getDefaultAuthenticatedRoute(user))
  }, [isError, isLoading, router, user])

  return <PlaybookRouteLoader />
}
