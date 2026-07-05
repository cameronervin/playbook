import type { ReactNode } from 'react'
import { cn } from '@/src/lib/utils/cn'

type BadgeTone = 'neutral' | 'brand' | 'info' | 'success' | 'warning' | 'danger'

interface BadgeProps {
  children: ReactNode
  className?: string
  tone?: BadgeTone
}

const toneClasses: Record<BadgeTone, string> = {
  neutral: 'border-border-strong bg-surface-raised text-fg-2',
  brand: 'border-transparent bg-brand-soft text-brand',
  info: 'border-transparent bg-info-bg text-info',
  success: 'border-transparent bg-success-bg text-success',
  warning: 'border-transparent bg-warning-bg text-warning',
  danger: 'border-transparent bg-danger-bg text-danger',
}

export function Badge({ children, className, tone = 'neutral' }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-2 rounded-pill border px-3 py-1 pb-ui-xs font-semibold',
        toneClasses[tone],
        className,
      )}
    >
      {children}
    </span>
  )
}
