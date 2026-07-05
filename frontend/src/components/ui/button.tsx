import type { ButtonHTMLAttributes } from 'react'
import { cn } from '@/src/lib/utils/cn'

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'
type ButtonSize = 'sm' | 'md' | 'lg'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
}

const variantClasses: Record<ButtonVariant, string> = {
  primary: 'border-transparent bg-brand text-fg-on-brand hover:bg-brand-hover',
  secondary: 'border-border-strong bg-transparent text-fg-1 hover:bg-surface-hover',
  ghost: 'border-transparent bg-transparent text-fg-2 hover:bg-surface-hover hover:text-fg-1',
  danger: 'border-transparent bg-danger-bg text-danger hover:bg-danger-bg/80',
}

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'pb-button-sm',
  md: 'pb-button-md',
  lg: 'pb-button-lg',
}

export function Button({ className, variant = 'primary', size = 'md', type = 'button', ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        'pb-focus-control inline-flex items-center justify-center gap-2 rounded-md border font-semibold transition active:translate-y-px disabled:cursor-not-allowed disabled:border-transparent disabled:bg-surface-raised disabled:text-fg-4',
        variantClasses[variant],
        sizeClasses[size],
        className,
      )}
      type={type}
      {...props}
    />
  )
}
