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

function SettingsHarness({ onOpenChange = vi.fn() }: { onOpenChange?: (open: boolean) => void }) {
  const [open, setOpen] = useState(true)
  return (
    <SettingsModal
      onOpenChange={(nextOpen) => {
        onOpenChange(nextOpen)
        setOpen(nextOpen)
      }}
      open={open}
      user={superAdminUser}
    />
  )
}

describe('SettingsModal', () => {
  it('renders the Claude profile settings layout with local draft fields', () => {
    render(<SettingsHarness />)

    const dialog = screen.getByRole('dialog', { name: /settings/i })
    const profileTab = within(dialog).getByRole('tab', { name: /profile/i })
    const securityTab = within(dialog).getByRole('tab', { name: /security & sso/i })
    const profileHeading = within(dialog).getByRole('heading', { name: /profile/i })
    const detailsHeading = within(dialog).getByRole('heading', { name: /details/i })

    expect(dialog).toBeInTheDocument()
    expect(dialog).toHaveClass('max-h-[calc(100dvh-32px)]')
    expect(dialog).not.toHaveClass('h-[min(660px,calc(100dvh-32px))]')
    expect(profileTab).toHaveAttribute('aria-selected', 'true')
    expect(profileTab).toHaveClass('pb-settings-nav-item')
    expect(securityTab).toHaveClass('pb-settings-nav-item')
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

  it('tracks unsaved profile changes and clears the local dirty state on save', async () => {
    render(<SettingsHarness />)

    await userEvent.clear(screen.getByLabelText(/job title/i))
    await userEvent.type(screen.getByLabelText(/job title/i), 'Assistant AD')

    expect(screen.getByText(/unsaved changes/i)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /save changes/i }))

    expect(screen.getByText(/all changes saved/i)).toBeInTheDocument()
  })

  it('renders the security and SSO design pane', async () => {
    render(<SettingsHarness />)

    await userEvent.click(screen.getByRole('tab', { name: /security & sso/i }))

    expect(screen.getByRole('heading', { name: /security & sso/i })).toHaveClass('pb-settings-header')
    expect(screen.getByRole('heading', { name: /single sign-on/i })).toHaveClass('pb-settings-section-title')
    expect(screen.getByText(/there's no password to manage/i)).toBeInTheDocument()
    expect(screen.getByText('Microsoft')).toBeInTheDocument()
    expect(screen.getByText('Microsoft')).toHaveClass('pb-settings-input')
    expect(screen.getByText('j.mitchell@okstate.edu')).toHaveClass('pb-settings-meta')
    expect(screen.getByText('Connected')).toHaveClass('pb-settings-badge')
    expect(screen.getByText('Google')).toBeInTheDocument()
    expect(screen.getByText('Not connected')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /connect google/i })).toBeInTheDocument()
    expect(screen.getByText(/this device · stillwater, ok/i)).toHaveClass('pb-settings-input')
    expect(screen.getByText(/chrome · last active just now/i)).toHaveClass('pb-settings-meta')
    expect(screen.getByText('Active')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /sign out of all other sessions/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /save changes/i })).not.toBeInTheDocument()
  })

  it('closes through Radix dialog escape handling', async () => {
    const onOpenChange = vi.fn()
    render(<SettingsHarness onOpenChange={onOpenChange} />)

    await userEvent.keyboard('{Escape}')

    expect(onOpenChange).toHaveBeenCalledWith(false)
    expect(screen.queryByRole('dialog', { name: /settings/i })).not.toBeInTheDocument()
  })
})
