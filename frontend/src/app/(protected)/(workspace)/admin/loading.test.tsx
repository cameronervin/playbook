import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AdminWorkspaceSkeleton } from '@/src/components/features/loading/PlaybookLoaders'
import AdminLoading from './loading'

describe('Admin loading route', () => {
  it('renders the full admin workspace skeleton', () => {
    render(<AdminLoading />)

    expect(screen.getByTestId('admin-workspace-skeleton')).toBeInTheDocument()
    expect(screen.getByTestId('admin-insights-skeleton')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Insights' })).toBeInTheDocument()
    expect(screen.getByText('Knowledge base')).toBeInTheDocument()
    expect(screen.getByText('Last 7 days')).toBeInTheDocument()
    expect(screen.getByText(/ai generated insights from user queries/i)).toBeInTheDocument()
    expect(screen.getByText('AI summary')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /common topics/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /risk flags/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /query volume/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /query review/i })).toBeInTheDocument()
    expect(screen.queryByText(/users & roles/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/loading admin/i)).not.toBeInTheDocument()
  })

  it('can render the super-admin users skeleton when role context is known', () => {
    render(<AdminWorkspaceSkeleton activeTab="users" isSuperAdmin />)

    expect(screen.getAllByText(/users & roles/i).length).toBeGreaterThanOrEqual(2)
    expect(screen.getByRole('heading', { name: /users & roles/i })).toBeInTheDocument()
    expect(screen.getByTestId('admin-users-skeleton')).toBeInTheDocument()
  })
})
