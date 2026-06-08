import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import WorkspaceLayout from './layout'

describe('Workspace route layout', () => {
  it('keeps workspace routes under the shared route group boundary', () => {
    render(
      <WorkspaceLayout>
        <p>Workspace child content</p>
      </WorkspaceLayout>,
    )

    expect(screen.getByTestId('workspace-route-group')).toBeInTheDocument()
    expect(screen.getByText('Workspace child content')).toBeInTheDocument()
  })
})
