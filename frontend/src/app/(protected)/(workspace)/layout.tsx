import type { ReactNode } from 'react'

interface WorkspaceLayoutProps {
  children: ReactNode
}

export default function WorkspaceLayout({ children }: WorkspaceLayoutProps) {
  return <div data-testid="workspace-route-group">{children}</div>
}
