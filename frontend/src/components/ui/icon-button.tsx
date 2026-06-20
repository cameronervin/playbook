import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { cn } from '@/src/lib/utils/cn'

type IconButtonVariant = 'surface' | 'ghost'
type IconButtonSize = 'sm' | 'md'

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode
  size?: IconButtonSize
  variant?: IconButtonVariant
}

const variantClasses: Record<IconButtonVariant, string> = {
  surface: 'border-border-strong bg-surface text-fg-2 hover:bg-surface-hover hover:text-fg-1',
  ghost: 'border-transparent bg-transparent text-fg-2 hover:bg-surface-hover hover:text-fg-1',
}

const sizeClasses: Record<IconButtonSize, string> = {
  sm: 'pb-icon-button-sm',
  md: 'pb-icon-button-md',
}

export function IconButton({
  className,
  children,
  size = 'md',
  type = 'button',
  variant = 'surface',
  ...props
}: IconButtonProps) {
  return (
    <button
      className={cn(
        'pb-focus-control rounded-md border transition active:translate-y-px disabled:cursor-not-allowed disabled:opacity-50',
        variantClasses[variant],
        sizeClasses[size],
        className,
      )}
      type={type}
      {...props}
    >
      {children}
    </button>
  )
}
