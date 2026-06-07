import type { ReactNode } from 'react'
import { cn } from '@/src/lib/utils/cn'
import { PlaybookMark } from '@/src/components/ui/brand'

interface AgentAvatarProps {
  children?: ReactNode
  className?: string
}

export function AgentAvatar({ children, className }: AgentAvatarProps) {
  return (
    <div
      className={cn(
        'flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-brand text-fg-on-brand',
        className,
      )}
    >
      {children ?? <PlaybookMark size={22} />}
    </div>
  )
}
