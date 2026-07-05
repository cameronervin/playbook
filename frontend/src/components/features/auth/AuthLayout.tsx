'use client'

import type { HTMLAttributes, ReactNode } from 'react'
import { HorizonBackground } from '@/src/components/features/common/HorizonBackground'
import { cn } from '@/src/lib/utils/cn'

interface AuthStageProps {
  children: ReactNode
  className?: string
}

export function AuthStage({ children, className }: AuthStageProps) {
  return (
    <main className={cn('pb-auth-stage', className)} data-testid="auth-stage">
      <HorizonBackground />
      {children}
    </main>
  )
}

type AuthCardProps = HTMLAttributes<HTMLElement>

export function AuthCard({ className, ...props }: AuthCardProps) {
  return (
    <section
      className={cn(
        'pb-auth-card animate-pb-rise relative z-10 w-full min-w-0 rounded-lg border border-border-strong bg-surface-raised px-8 pb-6 pt-16 shadow-lg',
        className,
      )}
      data-testid="auth-card"
      {...props}
    />
  )
}
