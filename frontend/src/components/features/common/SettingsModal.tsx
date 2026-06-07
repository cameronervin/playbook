'use client'

import { Dialog, Switch } from '@/src/components/ui'

interface SettingsModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  name?: string
  email?: string
}

export function SettingsModal({ open, onOpenChange, name, email }: SettingsModalProps) {
  return (
    <Dialog
      description="Manage the MVP account sections available for this phase."
      onOpenChange={onOpenChange}
      open={open}
      title="Settings"
    >
      <div className="grid gap-5">
        <section className="rounded-md border border-border-strong bg-surface p-4">
          <h3 className="text-sm font-semibold text-fg-1">Profile</h3>
          <p className="mt-2 text-sm text-fg-3">{name ?? 'Playbook user'}</p>
          <p className="text-xs text-fg-4">{email ?? 'Signed in with SSO'}</p>
        </section>
        <section className="rounded-md border border-border-strong bg-surface p-4">
          <h3 className="text-sm font-semibold text-fg-1">Security & SSO</h3>
          <p className="mt-2 text-sm text-fg-3">Authentication is managed through Google or Microsoft SSO.</p>
          <div className="mt-4">
            <Switch checked label="SSO session enabled" onCheckedChange={() => undefined} />
          </div>
        </section>
      </div>
    </Dialog>
  )
}
