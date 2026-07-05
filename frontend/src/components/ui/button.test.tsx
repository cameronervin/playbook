import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Button } from '@/src/components/ui/button'

describe('Button', () => {
  it('uses the compact Playbook control sizing for small buttons', () => {
    render(<Button size="sm">Regenerate</Button>)

    expect(screen.getByRole('button', { name: /regenerate/i })).toHaveClass(
      'pb-button-sm',
      'pb-focus-control',
    )
  })
})
