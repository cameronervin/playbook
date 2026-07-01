'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { BrandLockup } from '@/src/components/ui'
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

  return (
    <main className="pb-stage flex min-h-dvh items-center justify-center p-6">
      <div className="flex flex-col items-center gap-4 text-center">
        <BrandLockup />
        <p className="pb-refresh-note">Opening Playbook</p>
      </div>
    </main>
  )
}
