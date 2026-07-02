import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import ProfileLoading from './loading'

describe('Profile loading route', () => {
  it('renders the profile-card skeleton inside the auth stage', () => {
    render(<ProfileLoading />)

    expect(screen.getByTestId('profile-card-skeleton')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /complete your profile/i })).toBeInTheDocument()
    expect(screen.getByText('Name')).toBeInTheDocument()
    expect(screen.getByText('Sport or team')).toBeInTheDocument()
    expect(screen.getByText(/i'm ready/i)).toBeInTheDocument()
    expect(screen.queryByText(/we just need a few more details/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /i'm ready/i })).not.toBeInTheDocument()
    expect(screen.queryByText(/loading profile/i)).not.toBeInTheDocument()
  })
})
