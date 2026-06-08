import type { ReactNode } from 'react'
import { AuthStage } from '@/src/components/features/auth/AuthLayout'

interface AuthLayoutProps {
  children: ReactNode
}

export default function AuthLayout({ children }: AuthLayoutProps) {
  return <AuthStage>{children}</AuthStage>
}
