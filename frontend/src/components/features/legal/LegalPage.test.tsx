import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { LegalPage } from '@/src/components/features/legal/LegalPage'
import { LEGAL_NAV_LINKS, LEGAL_PAGES } from '@/src/lib/legalContent'

describe('LegalPage', () => {
  it('renders a Playbook legal page with the full legal navigation', () => {
    render(<LegalPage page={LEGAL_PAGES.privacy} />)

    expect(screen.getByText('Playbook')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /back to login/i })).toHaveAttribute('href', '/login')
    expect(screen.getByRole('heading', { name: /privacy policy/i })).toBeInTheDocument()
    expect(screen.getByText(/last updated/i)).toHaveTextContent('July 2, 2026')

    const nav = screen.getByRole('navigation', { name: /legal pages/i })

    for (const link of LEGAL_NAV_LINKS) {
      expect(within(nav).getByRole('link', { name: link.label })).toHaveAttribute('href', link.href)
    }

    expect(screen.getByRole('heading', { name: /information we process/i })).toBeInTheDocument()
    expect(screen.getByText(/review this content with counsel before production launch/i)).toBeInTheDocument()
  })
})
