import type { HTMLAttributes } from 'react'
import { cn } from '@/src/lib/utils/cn'

interface SurfaceProps extends HTMLAttributes<HTMLDivElement> {
  interactive?: boolean
}

export function Surface({ className, interactive = false, ...props }: SurfaceProps) {
  return (
    <div
      className={cn(
        'rounded-lg border border-border-strong bg-surface-raised shadow-sm',
        interactive && 'transition hover:border-border-brand hover:bg-surface-hover',
        className,
      )}
      {...props}
    />
  )
}
