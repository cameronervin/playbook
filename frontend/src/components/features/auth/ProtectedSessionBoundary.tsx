'use client'

import { useCurrentUser } from '@/src/hooks/useAuth'
import { useSessionActivity } from '@/src/hooks/useSessionActivity'

interface ProtectedSessionBoundaryProps {
  children: React.ReactNode
}

export function ProtectedSessionBoundary({ children }: ProtectedSessionBoundaryProps) {
  const { data: user, isLoading } = useCurrentUser()

  useSessionActivity({ enabled: Boolean(user) && !isLoading })

  return children
}
