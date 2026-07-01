import { beforeEach, describe, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ProfileScreen } from '@/src/components/features/profile/ProfileScreen'

const push = vi.fn()
const mutateAsync = vi.fn()

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push }),
}))

const currentUserMock = vi.hoisted(() => ({
  isLoading: false,
}))

vi.mock('@/src/hooks/useAuth', () => ({
  useCurrentUser: () => ({
    data: currentUserMock.isLoading ? undefined : { name: 'Jordan Athlete', email: 'athlete@example.com' },
    isLoading: currentUserMock.isLoading,
  }),
}))

vi.mock('@/src/hooks/useProfile', () => ({
  useUpdateProfile: () => ({
    mutateAsync,
    isPending: false,
    error: null,
  }),
}))

function renderProfile() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <ProfileScreen />
    </QueryClientProvider>,
  )
}

const globalsCss = readFileSync(resolve(process.cwd(), 'src/app/globals.css'), 'utf8')

describe('ProfileScreen', () => {
  beforeEach(() => {
    currentUserMock.isLoading = false
    mutateAsync.mockReset()
    push.mockReset()
  })

  it('renders a shaped profile skeleton while current user data resolves', () => {
    currentUserMock.isLoading = true

    renderProfile()

    expect(screen.getByTestId('profile-card-skeleton')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /complete your profile/i })).toBeInTheDocument()
    expect(screen.getByText('Name')).toBeInTheDocument()
    expect(screen.getByText('Sport or team')).toBeInTheDocument()
    expect(screen.queryByText(/we just need a few more details/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /i'm ready/i })).not.toBeInTheDocument()
  })

  it('renders profile completion inside the shared auth shell', () => {
    renderProfile()

    const authCard = screen.getByTestId('auth-card')
    const brandLockup = screen.getByText('Playbook').closest('div')
    const heading = screen.getByRole('heading', { name: /complete your profile/i })
    const description = screen.getByText(/we just need a few more details/i)
    const nameField = screen.getByLabelText(/name/i)
    const sportField = screen.getByLabelText(/sport or team/i)
    const continueButton = screen.getByRole('button', { name: /i'm ready/i })
    const form = continueButton.closest('form')

    expect(authCard).toBeInTheDocument()
    expect(authCard).not.toHaveClass('pb-auth-card-wide')
    expect(brandLockup).toHaveClass('justify-center')
    expect(heading).toHaveClass('pb-auth-heading')
    expect(description).toHaveClass('pb-auth-copy')
    expect(form).toHaveClass('pb-auth-profile-form')
    expect(nameField.closest('label')).toHaveClass('pb-auth-label', 'pb-auth-profile-field')
    expect(nameField).toHaveClass('pb-auth-profile-input')
    expect(nameField).not.toHaveClass('pb-auth-control')
    expect(nameField).not.toHaveClass('pb-auth-input')
    expect(sportField).toHaveAttribute('placeholder', 'Basketball')
    expect(sportField.closest('label')).toHaveClass('pb-auth-label', 'pb-auth-profile-field')
    expect(sportField).toHaveClass('pb-auth-profile-input')
    expect(sportField).not.toHaveClass('pb-auth-control')
    expect(sportField).not.toHaveClass('pb-auth-input')
    expect(continueButton).toHaveClass('pb-auth-profile-submit')
    expect(continueButton).not.toHaveClass('pb-auth-control')
  })

  it('defines profile auth controls globally with fixed centered heights', () => {
    const profileInputCss = globalsCss.match(/\.pb-auth-profile-input\s*{[^}]*}/s)?.[0] ?? ''
    const profileSubmitCss = globalsCss.match(/\.pb-auth-profile-submit\s*{[^}]*}/s)?.[0] ?? ''

    expect(globalsCss).toMatch(/\.pb-auth-profile-form\s*{/)
    expect(globalsCss).toMatch(/\.pb-auth-profile-field\s*{/)
    expect(profileInputCss).toMatch(/height:\s*var\(--spacing-auth-control\);/)
    expect(profileInputCss).toMatch(/padding:\s*0 16px;/)
    expect(profileInputCss).toMatch(/font-size:\s*16px;/)
    expect(profileInputCss).not.toMatch(/padding-bottom/)
    expect(profileSubmitCss).toMatch(/align-items:\s*center;/)
    expect(profileSubmitCss).toMatch(/display:\s*inline-flex;/)
    expect(profileSubmitCss).toMatch(/height:\s*var\(--spacing-auth-control\);/)
    expect(profileSubmitCss).toMatch(/justify-content:\s*center;/)
    expect(profileSubmitCss).toMatch(/padding:\s*0 24px;/)
    expect(profileSubmitCss).not.toMatch(/padding-bottom/)
  })

  it('submits athlete profile completion and follows next route', async () => {
    mutateAsync.mockResolvedValueOnce({ next_route: '/chat' })
    renderProfile()

    await userEvent.clear(screen.getByLabelText(/name/i))
    await userEvent.type(screen.getByLabelText(/name/i), 'Jordan Athlete')
    await userEvent.type(screen.getByLabelText(/sport/i), 'Basketball')
    await userEvent.click(screen.getByRole('button', { name: /i'm ready/i }))

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith({
        name: 'Jordan Athlete',
        sport_team: 'Basketball',
        selected_role: 'athlete',
      })
      expect(push).toHaveBeenCalledWith('/chat')
    })
  })
})
