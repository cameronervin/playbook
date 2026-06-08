import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import AdminLoading from './loading'

describe('Admin loading route', () => {
  it('renders the full admin workspace skeleton', () => {
    render(<AdminLoading />)

    expect(screen.getByTestId('admin-workspace-skeleton')).toBeInTheDocument()
    expect(screen.getByTestId('admin-insights-skeleton')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Insights' })).toBeInTheDocument()
    expect(screen.getByText('Knowledge base')).toBeInTheDocument()
    expect(screen.getByText('Last 7 days')).toBeInTheDocument()
    expect(screen.getByText('AI summary')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /common topics/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /risk flags/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /query volume/i })).toBeInTheDocument()
    expect(screen.queryByText(/ai generated insights from user queries/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/users & roles/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/loading admin/i)).not.toBeInTheDocument()
  })
})
