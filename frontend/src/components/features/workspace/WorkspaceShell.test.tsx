import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { WorkspaceShell, WorkspaceSidePanel } from '@/src/components/features/workspace/WorkspaceShell'

describe('WorkspaceShell', () => {
  it('renders a shared left rail, main workspace, and optional side panel', () => {
    render(
      <WorkspaceShell
        leftRail={<nav aria-label="Test rail">Rail</nav>}
        main={<section aria-label="Test workspace">Main</section>}
        sidePanel={<WorkspaceSidePanel aria-label="Test panel">Panel</WorkspaceSidePanel>}
      />,
    )

    expect(screen.getByTestId('workspace-shell')).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: /test rail/i })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: /test workspace/i })).toBeInTheDocument()
    expect(screen.getByRole('complementary', { name: /test panel/i })).toBeInTheDocument()
  })
})
