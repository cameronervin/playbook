import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SettingsModal } from '@/src/components/features/common/SettingsModal'
import type { CurrentUser } from '@/src/types/auth'

const superAdminUser: Pick<CurrentUser, 'name' | 'email' | 'role' | 'sport_team'> = {
  name: 'Jordan Mitchell',
  email: 'j.mitchell@okstate.edu',
  role: 'super_admin',
  sport_team: 'OSU Athletics',
}

function SettingsHarness({
  onOpenChange = vi.fn(),
  user = superAdminUser,
}: {
  onOpenChange?: (open: boolean) => void
  user?: Pick<CurrentUser, 'name' | 'email' | 'role' | 'sport_team'>
}) {
  const [open, setOpen] = useState(true)
  return (
    <SettingsModal
      onOpenChange={(nextOpen) => {
        onOpenChange(nextOpen)
        setOpen(nextOpen)
      }}
      open={open}
      user={user}
    />
  )
}

describe('SettingsModal', () => {
  it('renders the Claude profile settings layout with local draft fields', () => {
    render(<SettingsHarness />)

    const dialog = screen.getByRole('dialog', { name: /settings/i })
    const profileTab = within(dialog).getByRole('tab', { name: /profile/i })
    const profileHeading = within(dialog).getByRole('heading', { name: /profile/i })
    const detailsHeading = within(dialog).getByRole('heading', { name: /details/i })

    expect(dialog).toBeInTheDocument()
    expect(dialog).toHaveClass('max-h-[calc(100dvh-32px)]')
    expect(dialog).not.toHaveClass('h-[min(660px,calc(100dvh-32px))]')
    expect(profileTab).toHaveAttribute('aria-selected', 'true')
    expect(profileTab).toHaveClass('pb-settings-nav-item')
    expect(profileHeading).toHaveClass('pb-settings-header')
    expect(detailsHeading).toHaveClass('pb-settings-section-title')
    expect(screen.getByLabelText(/full name/i)).toHaveValue('Jordan Mitchell')
    expect(screen.getByLabelText(/full name/i)).toHaveClass('pb-settings-input')
    expect(screen.getByLabelText(/job title/i)).toHaveValue('Director of Operations')
    expect(screen.getByLabelText(/department/i)).toHaveValue('Athletics Administration')
    expect(screen.getByLabelText(/email/i)).toHaveValue('j.mitchell@okstate.edu')
    expect(screen.getByLabelText(/role/i)).toHaveValue('Super admin')
    expect(screen.getAllByText('SSO')).toHaveLength(2)
    expect(screen.getByText(/all changes saved/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /save changes/i })).toBeInTheDocument()
  })

  it('does not render the removed security and SSO pane', () => {
    render(<SettingsHarness />)

    const dialog = screen.getByRole('dialog', { name: /settings/i })

    expect(within(dialog).queryByRole('tab', { name: /security & sso/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: /single sign-on/i })).not.toBeInTheDocument()
    expect(screen.queryByText(/there's no password to manage/i)).not.toBeInTheDocument()
    expect(screen.queryByText('Microsoft')).not.toBeInTheDocument()
    expect(screen.queryByText('Google')).not.toBeInTheDocument()
    expect(screen.queryByText('Connected')).not.toBeInTheDocument()
    expect(screen.queryByText('Not connected')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /connect google/i })).not.toBeInTheDocument()
    expect(screen.queryByText(/this device/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/chrome/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /sign out of all other sessions/i })).not.toBeInTheDocument()
  })

  it.each([
    ['athlete', 'Athlete'],
    ['admin', 'Department admin'],
    ['super_admin', 'Super admin'],
  ] as const)('removes security and SSO settings for %s users', (role, roleLabel) => {
    render(<SettingsHarness user={{ ...superAdminUser, role }} />)

    const dialog = screen.getByRole('dialog', { name: /settings/i })

    expect(within(dialog).getByRole('tab', { name: /profile/i })).toBeInTheDocument()
    expect(within(dialog).getByLabelText(/role/i)).toHaveValue(roleLabel)
    expect(within(dialog).queryByRole('tab', { name: /security & sso/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: /single sign-on/i })).not.toBeInTheDocument()
  })

  it('tracks unsaved profile changes and clears the local dirty state on save', async () => {
    render(<SettingsHarness />)

    await userEvent.clear(screen.getByLabelText(/job title/i))
    await userEvent.type(screen.getByLabelText(/job title/i), 'Assistant AD')

    expect(screen.getByText(/unsaved changes/i)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /save changes/i }))

    expect(screen.getByText(/all changes saved/i)).toBeInTheDocument()
  })

  it('closes through Radix dialog escape handling', async () => {
    const onOpenChange = vi.fn()
    render(<SettingsHarness onOpenChange={onOpenChange} />)

    await userEvent.keyboard('{Escape}')

    expect(onOpenChange).toHaveBeenCalledWith(false)
    expect(screen.queryByRole('dialog', { name: /settings/i })).not.toBeInTheDocument()
  })
})
