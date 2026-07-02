import type { ReactNode } from 'react'
import { AuthStage } from '@/src/components/features/auth/AuthLayout'

interface ProtectedAuthLayoutProps {
  children: ReactNode
}

export default function ProtectedAuthLayout({ children }: ProtectedAuthLayoutProps) {
  return <AuthStage>{children}</AuthStage>
}
