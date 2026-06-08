import type { HTMLAttributes, ReactNode } from 'react'
import { cn } from '@/src/lib/utils/cn'

interface WorkspaceShellProps {
  leftRail: ReactNode
  main: ReactNode
  sidePanel?: ReactNode
}

export function WorkspaceShell({ leftRail, main, sidePanel }: WorkspaceShellProps) {
  return (
    <main className="flex h-dvh overflow-hidden bg-bg-base text-fg-1" data-testid="workspace-shell">
      {leftRail}
      {main}
      {sidePanel}
    </main>
  )
}

type WorkspaceSidePanelProps = HTMLAttributes<HTMLElement>

export function WorkspaceSidePanel({ className, ...props }: WorkspaceSidePanelProps) {
  return (
    <aside
      className={cn(
        'hidden h-dvh w-[320px] shrink-0 flex-col border-l border-border bg-bg-page text-fg-1 lg:flex',
        className,
      )}
      role="complementary"
      {...props}
    />
  )
}
