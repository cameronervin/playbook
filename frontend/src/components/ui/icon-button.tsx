import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { cn } from '@/src/lib/utils/cn'

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode
}

export function IconButton({ className, children, type = 'button', ...props }: IconButtonProps) {
  return (
    <button
      className={cn(
        'inline-flex h-10 w-10 items-center justify-center rounded-md border border-border-strong bg-surface text-fg-2 transition hover:bg-surface-hover hover:text-fg-1 active:translate-y-px disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
      type={type}
      {...props}
    >
      {children}
    </button>
  )
}
