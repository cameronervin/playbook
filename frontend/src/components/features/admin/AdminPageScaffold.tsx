import type { ReactNode } from 'react'
import { cn } from '@/src/lib/utils/cn'

interface AdminPageScaffoldProps {
  actions?: ReactNode
  children: ReactNode
  contentClassName?: string
  contentMaxWidthClassName?: string
  subtitle?: string
  title: string
  toolbar?: ReactNode
}

export function AdminPageScaffold({
  actions,
  children,
  contentClassName,
  contentMaxWidthClassName = 'pb-admin-content-width',
  subtitle,
  title,
  toolbar,
}: AdminPageScaffoldProps) {
  return (
    <div className="flex min-h-full flex-col">
      <header className="relative shrink-0 border-b border-border bg-bg-base px-7">
        <div className="admin-grid" aria-hidden="true" />
        <div className="relative z-10 flex min-h-[68px] items-center gap-5">
          <div className="min-w-0">
            <h1 className="pb-page-title">{title}</h1>
            {subtitle && <p className="pb-page-subtitle mt-0.5">{subtitle}</p>}
          </div>
          {actions && <div className="ml-auto flex items-center gap-2.5">{actions}</div>}
        </div>
      </header>

      {toolbar && (
        <div className="shrink-0 border-b border-border bg-bg-base px-7 py-3" data-testid="admin-page-toolbar">
          <div className={cn('mx-auto w-full', contentMaxWidthClassName)}>{toolbar}</div>
        </div>
      )}

      <div className={cn('flex-1 px-7 py-4', contentClassName)}>
        <div className={cn('mx-auto w-full', contentMaxWidthClassName)}>{children}</div>
      </div>
    </div>
  )
}
