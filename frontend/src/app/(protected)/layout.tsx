import type { ReactNode } from 'react'
import { ProtectedSessionBoundary } from '@/src/components/features/auth/ProtectedSessionBoundary'

interface ProtectedLayoutProps {
  children: ReactNode
}

export default function ProtectedLayout({ children }: ProtectedLayoutProps) {
  return <ProtectedSessionBoundary>{children}</ProtectedSessionBoundary>
}
