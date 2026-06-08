'use client'

import * as DialogPrimitive from '@radix-ui/react-dialog'
import * as TabsPrimitive from '@radix-ui/react-tabs'
import type { ChangeEvent, ReactNode } from 'react'
import { useEffect, useState } from 'react'
import { Check, Lock, LogOut, Mail, Monitor, ShieldCheck, User, X } from 'lucide-react'
import { Button, GoogleLogo, IconButton, MicrosoftLogo } from '@/src/components/ui'
import { cn } from '@/src/lib/utils/cn'
import type { CurrentUser, UserRole } from '@/src/types/auth'

type SettingsSection = 'profile' | 'security'

interface SettingsModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  user?: Pick<CurrentUser, 'name' | 'email' | 'role' | 'sport_team'>
}

interface ProfileDraft {
  department: string
  email: string
  jobTitle: string
  name: string
  roleLabel: string
}

const SETTINGS_NAV: Array<{ id: SettingsSection; icon: typeof User; label: string }> = [
  { id: 'profile', icon: User, label: 'Profile' },
  { id: 'security', icon: ShieldCheck, label: 'Security & SSO' },
]

export function SettingsModal({ open, onOpenChange, user }: SettingsModalProps) {
  const [section, setSection] = useState<SettingsSection>('profile')
  const [dirty, setDirty] = useState(false)
  const [draft, setDraft] = useState<ProfileDraft>(() => getProfileDraft(user))

  useEffect(() => {
    if (!open) return
    setSection('profile')
    setDirty(false)
    setDraft(getProfileDraft(user))
  }, [open, user])

  const activeLabel = SETTINGS_NAV.find((item) => item.id === section)?.label ?? 'Profile'

  const patchDraft = (field: keyof Pick<ProfileDraft, 'department' | 'jobTitle' | 'name'>, value: string) => {
    setDraft((current) => ({ ...current, [field]: value }))
    setDirty(true)
  }

  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-bg-void/70 backdrop-blur-[3px]" />
        <DialogPrimitive.Content className="fixed left-1/2 top-1/2 z-50 flex max-h-[calc(100dvh-32px)] w-[min(880px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 overflow-hidden rounded-lg border border-border-strong bg-surface-raised shadow-lg outline-none max-md:flex-col">
          <DialogPrimitive.Description className="sr-only">
            Manage your Playbook profile and single sign-on settings.
          </DialogPrimitive.Description>
          <TabsPrimitive.Root
            className="flex min-h-0 max-h-[calc(100dvh-32px)] w-full max-md:flex-col"
            onValueChange={(value) => setSection(value as SettingsSection)}
            orientation="vertical"
            value={section}
          >
            <aside className="flex w-[218px] shrink-0 flex-col border-r border-border bg-bg-page px-3 py-[18px] max-md:w-full max-md:border-b max-md:border-r-0 max-md:p-3">
              <DialogPrimitive.Title className="pb-settings-title px-2.5 pb-3.5 pt-1 max-md:pb-3">
                Settings
              </DialogPrimitive.Title>
              <TabsPrimitive.List
                aria-label="Settings sections"
                className="flex flex-col gap-px max-md:grid max-md:grid-cols-2 max-[420px]:grid-cols-1"
              >
                {SETTINGS_NAV.map((item) => (
                  <SettingsTab item={item} key={item.id} />
                ))}
              </TabsPrimitive.List>
            </aside>

            <section className="flex min-w-0 flex-1 flex-col">
              <header className="flex h-[60px] shrink-0 items-center border-b border-border px-[22px] max-md:h-14 max-md:px-4">
                <h2 className="pb-settings-header">
                  {activeLabel}
                </h2>
                <DialogPrimitive.Close asChild>
                  <IconButton
                    aria-label="Close settings"
                    className="ml-auto h-[34px] w-[34px] border-transparent bg-transparent text-fg-3 hover:bg-surface-hover"
                  >
                    <X className="h-[18px] w-[18px]" />
                  </IconButton>
                </DialogPrimitive.Close>
              </header>

              <div className="min-h-0 overflow-y-auto px-6 py-[22px] max-md:px-4">
                <TabsPrimitive.Content className="m-0 outline-none" forceMount hidden={section !== 'profile'} value="profile">
                  <ProfilePane draft={draft} onPatch={patchDraft} />
                </TabsPrimitive.Content>
                <TabsPrimitive.Content className="m-0 outline-none" forceMount hidden={section !== 'security'} value="security">
                  <SecurityPane email={draft.email} />
                </TabsPrimitive.Content>
              </div>

              {section === 'profile' && (
                <footer className="flex shrink-0 items-center gap-3 border-t border-border bg-surface px-[22px] py-3 max-md:flex-wrap max-md:px-4">
                  <div className={cn('pb-settings-meta flex items-center gap-2', dirty ? 'text-fg-2' : 'text-fg-4')}>
                    {dirty && <span className="h-1.5 w-1.5 rounded-full bg-warning" aria-hidden="true" />}
                    {dirty ? 'Unsaved changes' : 'All changes saved'}
                  </div>
                  <div className="ml-auto flex gap-2.5">
                    <Button onClick={() => onOpenChange(false)} size="sm" variant="secondary">
                      Cancel
                    </Button>
                    <Button onClick={() => setDirty(false)} size="sm">
                      <Check className="h-4 w-4" />
                      Save changes
                    </Button>
                  </div>
                </footer>
              )}
            </section>
          </TabsPrimitive.Root>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}

interface SettingsTabProps {
  item: (typeof SETTINGS_NAV)[number]
}

function SettingsTab({ item }: SettingsTabProps) {
  const Icon = item.icon
  return (
    <TabsPrimitive.Trigger
      className="pb-settings-nav-item flex w-full items-center gap-[11px] rounded-sm px-[11px] py-2.5 text-left font-medium text-fg-2 outline-none transition hover:bg-surface-hover hover:text-fg-1 focus-visible:shadow-focus data-[state=active]:bg-brand-soft data-[state=active]:font-semibold data-[state=active]:text-brand data-[state=active]:[&_svg]:text-brand"
      value={item.id}
    >
      <Icon className="h-[17px] w-[17px] shrink-0 text-fg-3" />
      <span className="min-w-0 truncate">{item.label}</span>
    </TabsPrimitive.Trigger>
  )
}

interface ProfilePaneProps {
  draft: ProfileDraft
  onPatch: (field: keyof Pick<ProfileDraft, 'department' | 'jobTitle' | 'name'>, value: string) => void
}

function ProfilePane({ draft, onPatch }: ProfilePaneProps) {
  return (
    <div>
      <Group title="Details">
        <Field label="Full name">
          <SettingsInput value={draft.name} onChange={(value) => onPatch('name', value)} />
        </Field>
        <div className="grid grid-cols-2 gap-3 max-md:grid-cols-1">
          <Field label="Job title">
            <SettingsInput value={draft.jobTitle} onChange={(value) => onPatch('jobTitle', value)} />
          </Field>
          <Field label="Department">
            <SettingsInput value={draft.department} onChange={(value) => onPatch('department', value)} />
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-3 max-md:grid-cols-1">
          <Field label="Email">
            <SettingsInput icon={<Mail className="h-4 w-4" />} readOnly value={draft.email} />
          </Field>
          <Field label="Role">
            <SettingsInput readOnly value={draft.roleLabel} />
          </Field>
        </div>
      </Group>
    </div>
  )
}

interface SecurityPaneProps {
  email: string
}

function SecurityPane({ email }: SecurityPaneProps) {
  return (
    <div>
      <Group
        description="Playbook uses SSO only - there's no password to manage. Your administrator controls which providers are available."
        title="Single sign-on"
      >
        <div className="grid gap-2.5">
          <ProviderRow connected logo={<MicrosoftLogo />} name="Microsoft" subLabel={email} />
          <ProviderRow logo={<GoogleLogo />} name="Google" subLabel="Not connected" />
        </div>
      </Group>
      <Group title="Active session">
        <div className="flex items-center gap-[13px] rounded-md border border-border bg-bg-base px-[15px] py-3.5">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-surface-hover text-fg-2">
            <Monitor className="h-[18px] w-[18px]" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="pb-settings-input truncate font-semibold text-fg-1">This device · Stillwater, OK</p>
            <p className="pb-settings-meta mt-0.5 truncate text-fg-3">Chrome · last active just now</p>
          </div>
          <StatusBadge>Active</StatusBadge>
        </div>
        <Button className="mt-3.5" size="sm" variant="danger">
          <LogOut className="h-4 w-4" />
          Sign out of all other sessions
        </Button>
      </Group>
    </div>
  )
}

interface GroupProps {
  children: ReactNode
  description?: string
  title: string
}

function Group({ children, description, title }: GroupProps) {
  return (
    <section className="mb-6">
      <h3 className="pb-settings-section-title">{title}</h3>
      {description && (
        <p className="pb-settings-meta mt-1 max-w-[460px] leading-5 text-fg-3">
          {description}
        </p>
      )}
      <div className={description ? 'mt-3.5' : 'mt-3'}>{children}</div>
    </section>
  )
}

interface FieldProps {
  children: ReactNode
  label: string
}

function Field({ children, label }: FieldProps) {
  return (
    <label className="mb-3.5 block">
      <span className="pb-settings-label mb-1.5 block">{label}</span>
      {children}
    </label>
  )
}

interface SettingsInputProps {
  icon?: ReactNode
  onChange?: (value: string) => void
  readOnly?: boolean
  value: string
}

function SettingsInput({ icon, onChange, readOnly = false, value }: SettingsInputProps) {
  const handleChange = (event: ChangeEvent<HTMLInputElement>) => onChange?.(event.target.value)
  return (
    <div
      className={cn(
        'pb-field-shell flex h-10 items-center gap-2.5 rounded-md border border-border-solid px-3 transition',
        readOnly ? 'bg-surface text-fg-3' : 'bg-bg-base text-fg-1',
      )}
    >
      {icon && <span className="shrink-0 text-fg-4">{icon}</span>}
      <input
        className={cn(
          'pb-settings-input min-w-0 flex-1 border-0 bg-transparent outline-none placeholder:text-fg-4',
          readOnly ? 'text-fg-3' : 'text-fg-1',
        )}
        onChange={handleChange}
        readOnly={readOnly}
        value={value}
      />
      {readOnly && (
        <span className="pb-settings-meta inline-flex shrink-0 items-center gap-1 text-fg-4">
          <Lock className="h-3 w-3" />
          SSO
        </span>
      )}
    </div>
  )
}

interface ProviderRowProps {
  connected?: boolean
  logo: ReactNode
  name: string
  subLabel: string
}

function ProviderRow({ connected = false, logo, name, subLabel }: ProviderRowProps) {
  return (
    <div
      className={cn(
        'flex items-center gap-[13px] rounded-md border bg-bg-base px-[15px] py-[13px]',
        connected ? 'border-border-strong' : 'border-border',
      )}
    >
      <div className="flex h-[34px] w-[34px] shrink-0 items-center justify-center rounded-sm border border-border bg-surface-raised">
        {logo}
      </div>
      <div className="min-w-0 flex-1">
        <p className="pb-settings-input truncate font-semibold text-fg-1">{name}</p>
        <p className="pb-settings-meta mt-px truncate text-fg-3">{subLabel}</p>
      </div>
      {connected ? (
        <StatusBadge>Connected</StatusBadge>
      ) : (
        <Button aria-label={`Connect ${name}`} size="sm" variant="secondary">
          Connect
        </Button>
      )}
    </div>
  )
}

function StatusBadge({ children }: { children: ReactNode }) {
  return (
    <span className="pb-settings-badge inline-flex shrink-0 items-center gap-2 rounded-pill border border-transparent bg-success-bg px-3 py-1 text-success">
      <span className="h-2 w-2 rounded-full bg-success" aria-hidden="true" />
      {children}
    </span>
  )
}

function getProfileDraft(user?: Pick<CurrentUser, 'name' | 'email' | 'role' | 'sport_team'>): ProfileDraft {
  const role = user?.role ?? 'athlete'
  const adminProfile = role === 'admin' || role === 'super_admin'
  return {
    department: adminProfile ? 'Athletics Administration' : user?.sport_team ?? 'OSU Athletics',
    email: user?.email ?? 'Signed in with SSO',
    jobTitle: adminProfile ? 'Director of Operations' : 'Student-athlete',
    name: user?.name ?? 'Playbook user',
    roleLabel: getRoleLabel(role),
  }
}

function getRoleLabel(role: UserRole) {
  if (role === 'super_admin') return 'Super admin'
  if (role === 'admin') return 'Department admin'
  return 'Athlete'
}
