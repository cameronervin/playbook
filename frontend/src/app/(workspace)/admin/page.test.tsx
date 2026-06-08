import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import AdminPage from './page'

vi.mock('@/src/components/features/admin/AdminShell', () => ({
  AdminShell: () => <div>Admin shell from workspace group</div>,
}))

describe('Workspace admin route', () => {
  it('renders the admin shell without changing the public URL segment', () => {
    render(<AdminPage />)

    expect(screen.getByText(/admin shell from workspace group/i)).toBeInTheDocument()
  })
})
