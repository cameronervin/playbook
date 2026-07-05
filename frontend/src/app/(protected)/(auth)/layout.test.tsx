import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import ProtectedAuthLayout from './layout'

describe('Protected auth route layout', () => {
  it('keeps protected auth routes inside the shared horizon stage', () => {
    render(
      <ProtectedAuthLayout>
        <p>Protected auth child content</p>
      </ProtectedAuthLayout>,
    )

    expect(screen.getByTestId('auth-stage')).toBeInTheDocument()
    expect(screen.getByTestId('horizon-background')).toBeInTheDocument()
    expect(screen.getByText('Protected auth child content')).toBeInTheDocument()
  })
})
