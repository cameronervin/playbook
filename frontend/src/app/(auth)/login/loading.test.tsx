import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import LoginLoading from './loading'

describe('Login loading route', () => {
  it('renders the auth-card provider skeletons', () => {
    render(<LoginLoading />)

    expect(screen.getByTestId('auth-loading-skeleton')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /log in to continue/i })).toBeInTheDocument()
    expect(screen.getAllByTestId('auth-provider-skeleton')).toHaveLength(2)
    expect(screen.getByText(/privacy policy/i)).toBeInTheDocument()
    expect(screen.getByText(/terms of service/i)).toBeInTheDocument()
    expect(screen.queryByText(/loading login/i)).not.toBeInTheDocument()
  })
})
