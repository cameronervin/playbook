import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import PrivacyPage from '@/src/app/privacy/page'
import TermsPage from '@/src/app/terms/page'
import CookiesPage from '@/src/app/cookies/page'
import SubprocessorsPage from '@/src/app/subprocessors/page'
import SecurityPage from '@/src/app/security/page'
import { GET as getSecurityTxt } from '@/src/app/.well-known/security.txt/route'

const routes = [
  { Component: PrivacyPage, heading: 'Privacy Policy', link: '/privacy' },
  { Component: TermsPage, heading: 'Terms of Service', link: '/terms' },
  { Component: CookiesPage, heading: 'Cookie Notice', link: '/cookies' },
  { Component: SubprocessorsPage, heading: 'Subprocessors', link: '/subprocessors' },
  { Component: SecurityPage, heading: 'Security', link: '/security' },
] as const

describe('legal routes', () => {
  it.each(routes)('renders $link as a public legal page', ({ Component, heading, link }) => {
    render(<Component />)

    expect(screen.getByRole('heading', { name: heading })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: heading })).toHaveAttribute('href', link)
    expect(screen.getByRole('link', { name: /back to login/i })).toHaveAttribute('href', '/login')
  })

  it('serves a plain-text security.txt from the well-known route', async () => {
    const response = getSecurityTxt()
    const text = await response.text()

    expect(response.headers.get('content-type')).toBe('text/plain; charset=utf-8')
    expect(text).toContain('Contact: mailto:security@playbook.example')
    expect(text).toContain('Policy: /security')
    expect(text).toContain('Expires: 2027-07-02T00:00:00.000Z')
  })
})
