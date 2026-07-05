import type { HTMLAttributes } from 'react'
import { cn } from '@/src/lib/utils/cn'

type SkeletonProps = HTMLAttributes<HTMLDivElement>

export function Skeleton({ className, ...props }: SkeletonProps) {
  return (
    <div
      aria-hidden="true"
      className={cn('pb-skeleton rounded-sm', className)}
      {...props}
    />
  )
}

interface SkeletonTextProps extends HTMLAttributes<HTMLDivElement> {
  lines?: number
  widths?: string[]
}

export function SkeletonText({ className, lines = 1, widths, ...props }: SkeletonTextProps) {
  return (
    <div aria-hidden="true" className={cn('grid gap-2', className)} {...props}>
      {Array.from({ length: lines }).map((_, index) => (
        <Skeleton
          className="h-3 rounded-pill"
          key={index}
          style={{ width: widths?.[index] ?? '100%' }}
        />
      ))}
    </div>
  )
}

interface SkeletonAvatarProps extends SkeletonProps {
  sizeClassName?: string
}

export function SkeletonAvatar({ className, sizeClassName = 'h-8 w-8', ...props }: SkeletonAvatarProps) {
  return <Skeleton className={cn(sizeClassName, 'rounded-md', className)} {...props} />
}

export function SkeletonButton({ className, ...props }: SkeletonProps) {
  return <Skeleton className={cn('h-9 rounded-md border border-border-strong', className)} {...props} />
}
