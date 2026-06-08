import type { InputHTMLAttributes, TextareaHTMLAttributes } from 'react'
import { cn } from '@/src/lib/utils/cn'

type InputProps = InputHTMLAttributes<HTMLInputElement>

export function Input({ className, ...props }: InputProps) {
  return (
    <input
      className={cn(
        'w-full rounded-md border border-border-strong bg-surface px-4 py-3 text-sm text-fg-1 placeholder:text-fg-4 transition focus:border-border-brand',
        className,
      )}
      {...props}
    />
  )
}

type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement>

export function Textarea({ className, ...props }: TextareaProps) {
  return (
    <textarea
      className={cn(
        'w-full resize-none rounded-md border border-border-strong bg-surface px-4 py-3 text-sm text-fg-1 placeholder:text-fg-4 transition focus:border-border-brand',
        className,
      )}
      {...props}
    />
  )
}
