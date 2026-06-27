'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { BrandLockup } from '@/src/components/ui'
import { useCurrentUser } from '@/src/hooks/useAuth'
import { ROUTES } from '@/src/lib/constants/config'

export default function RootRedirect() {
  const router = useRouter()
  const { data: user, isError, isLoading } = useCurrentUser()

  useEffect(() => {
    if (isLoading) return
    if (isError || !user) {
      router.replace(ROUTES.login)
      return
    }
    if (user.role === 'athlete' && !user.profile_complete) {
      router.replace(ROUTES.profile)
      return
    }
    if (user.role === 'admin' || user.role === 'super_admin') {
      router.replace(ROUTES.admin)
      return
    }
    router.replace(ROUTES.chat)
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
