import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import RootLoading from './loading'

describe('Root loading route', () => {
  it('renders the minimal Playbook route loader', () => {
    render(<RootLoading />)

    expect(screen.getByTestId('playbook-brand-loader')).toBeInTheDocument()
    expect(screen.getByRole('status', { name: /loading playbook/i })).toBeInTheDocument()
    expect(screen.getByText(/^Loading$/i)).toBeInTheDocument()
    expect(screen.queryByTestId('root-redirect-loader')).not.toBeInTheDocument()
    expect(screen.queryByText(/opening playbook/i)).not.toBeInTheDocument()
  })
})
