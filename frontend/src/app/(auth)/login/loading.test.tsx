import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { render, screen } from '@testing-library/react'
import LoginLoading from './loading'

const globalsCss = readFileSync(resolve(process.cwd(), 'src/app/globals.css'), 'utf8')

describe('Login loading route', () => {
  it('renders the minimal pre-login brand loader', () => {
    render(<LoginLoading />)

    expect(screen.getByTestId('playbook-brand-loader')).toBeInTheDocument()
    expect(screen.getByRole('status', { name: /loading playbook/i })).toBeInTheDocument()
    expect(screen.getByText(/^Loading$/i)).toBeInTheDocument()
    expect(screen.queryByTestId('auth-loading-skeleton')).not.toBeInTheDocument()
    expect(screen.queryByTestId('auth-provider-skeleton')).not.toBeInTheDocument()
    expect(screen.queryByTestId('auth-card')).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: /log in to continue/i })).not.toBeInTheDocument()
    expect(screen.queryByText(/privacy policy/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/terms of service/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/loading login/i)).not.toBeInTheDocument()
  })

  it('defines the plain token-backed route loader and dot animation globally', () => {
    expect(globalsCss).toMatch(/\.pb-route-loader-stage\s*{[^}]*background:\s*var\(--bg-page\);/s)
    expect(globalsCss).toMatch(/\.pb-route-loader-mark\s*{[^}]*color:\s*var\(--fg-1\);/s)
    expect(globalsCss).toMatch(/\.pb-route-loader-text::after\s*{[^}]*animation:\s*pb-loading-dots/s)
    expect(globalsCss).toMatch(/@keyframes pb-loading-dots/)
    expect(globalsCss).toMatch(/@media \(prefers-reduced-motion:\s*reduce\)\s*{[^}]*\.pb-route-loader-text::after/s)
    expect(globalsCss).toMatch(/@media \(prefers-reduced-motion:\s*reduce\)\s*{[^}]*content:\s*" \.\.\."/s)
  })
})
