import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import AuthLayout from './layout'

describe('Auth route layout', () => {
  it('wraps auth routes with the shared horizon stage', () => {
    render(
      <AuthLayout>
        <p>Auth child content</p>
      </AuthLayout>,
    )

    expect(screen.getByTestId('auth-stage')).toBeInTheDocument()
    expect(screen.getByTestId('horizon-background')).toBeInTheDocument()
    expect(screen.getByText('Auth child content')).toBeInTheDocument()
  })
})
