'use client'

import { useMemo, useState } from 'react'
import * as DropdownMenuPrimitive from '@radix-ui/react-dropdown-menu'
import { Check, ChevronDown, Lock, Search, Shield, ShieldCheck, User } from 'lucide-react'
import { AdminPageScaffold } from '@/src/components/features/admin/AdminPageScaffold'
import { AdminUsersSkeleton } from '@/src/components/features/loading/PlaybookLoaders'
import { Badge } from '@/src/components/ui'
import { cn } from '@/src/lib/utils/cn'
import type { AdminUser } from '@/src/types/admin'
import type { UserRole } from '@/src/types/auth'

interface AdminUsersPanelProps {
  currentUserId?: string
  isError?: boolean
  isFetching?: boolean
  isLoading?: boolean
  onRoleChange: (id: string, role: UserRole) => void
  users: AdminUser[]
}

interface RoleMeta {
  icon: typeof Shield
  label: string
  tone: 'neutral' | 'brand' | 'info'
}

const roleMeta: Record<UserRole, RoleMeta> = {
  super_admin: { label: 'Super admin', tone: 'brand', icon: Shield },
  admin: { label: 'Admin', tone: 'info', icon: ShieldCheck },
  athlete: { label: 'Athlete', tone: 'neutral', icon: User },
}

const roleOptions: Array<{ label: string; role: UserRole }> = [
  { role: 'athlete', label: 'Set as athlete' },
  { role: 'admin', label: 'Promote to admin' },
  { role: 'super_admin', label: 'Promote to super admin' },
]

export function AdminUsersPanel({
  currentUserId,
  isError = false,
  isFetching = false,
  isLoading = false,
  onRoleChange,
  users,
}: AdminUsersPanelProps) {
  const [query, setQuery] = useState('')
  const adminCount = users.filter((user) => user.role === 'admin' || user.role === 'super_admin').length
  const filteredUsers = useMemo(() => {
    const normalized = query.trim().toLowerCase()
    if (!normalized) return users

    return users.filter((user) => {
      const searchable = `${user.name} ${user.email}`.toLowerCase()
      return searchable.includes(normalized)
    })
  }, [query, users])

  return (
    <AdminPageScaffold
      contentClassName="py-[18px]"
      contentMaxWidthClassName="max-w-[880px]"
      subtitle={isLoading ? undefined : `${users.length} ${users.length === 1 ? 'user' : 'users'} · ${adminCount} with admin access`}
      title="Users & roles"
    >
      {isLoading ? (
        <AdminUsersSkeleton />
      ) : (
        <>
          {isFetching && (
            <p className="pb-refresh-note mb-3">
              <span className="pb-spin h-2 w-2 rounded-full border border-info border-t-transparent" />
              Refreshing users
            </p>
          )}
          {isError && (
            <p className="mb-3 rounded-md border border-danger/30 bg-danger-bg px-3 py-2 text-sm text-danger">
              Users could not be refreshed.
            </p>
          )}
      <section
        aria-label="Users and roles table"
        className="overflow-hidden rounded-lg border border-border-strong bg-surface"
      >
        <div className="border-b border-border bg-bg-base px-4 py-3">
          <label className="pb-admin-table-search pb-field-shell">
            <Search className="pb-admin-table-search-icon" />
            <span className="sr-only">Search users</span>
            <input
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search users..."
              type="search"
              value={query}
            />
          </label>
        </div>

        <div className="hidden grid-cols-[2fr_1.2fr_150px] gap-3.5 border-b border-border bg-bg-base px-4 py-[11px] md:grid">
          {['User', 'Role', ''].map((header) => (
            <span
              className="text-[10.5px] font-bold uppercase tracking-[0.06em] text-fg-4"
              key={header || 'actions'}
            >
              {header}
            </span>
          ))}
        </div>

        {users.length === 0 && <EmptyUsersMessage>No users returned yet.</EmptyUsersMessage>}
        {users.length > 0 && filteredUsers.length === 0 && <EmptyUsersMessage>No users match that search.</EmptyUsersMessage>}
        {filteredUsers.map((adminUser, index) => (
          <UserRow
            currentUserId={currentUserId}
            key={adminUser.id}
            last={index === filteredUsers.length - 1}
            onRoleChange={onRoleChange}
            user={adminUser}
          />
        ))}
      </section>
        </>
      )}
    </AdminPageScaffold>
  )
}

function EmptyUsersMessage({ children }: { children: string }) {
  return <div className="p-5 text-sm text-fg-3">{children}</div>
}

interface UserRowProps {
  currentUserId?: string
  last: boolean
  onRoleChange: (id: string, role: UserRole) => void
  user: AdminUser
}

function UserRow({ currentUserId, last, onRoleChange, user }: UserRowProps) {
  const isCurrentUser = Boolean(currentUserId && user.id === currentUserId)

  return (
    <div
      className={cn(
        'grid gap-3.5 px-4 py-[13px] md:grid-cols-[2fr_1.2fr_150px] md:items-center',
        !last && 'border-b border-border',
      )}
    >
      <div className="flex min-w-0 items-center gap-3">
        <span
          className={cn(
            'flex h-[34px] w-[34px] shrink-0 items-center justify-center rounded-md font-display text-[13px] font-extrabold',
            isCurrentUser ? 'bg-brand text-fg-on-brand' : 'bg-surface-hover text-fg-2',
          )}
          aria-hidden="true"
        >
          {getInitials(user.name)}
        </span>
        <span className="min-w-0">
          <span className="flex min-w-0 items-center gap-[7px]">
            <span className="pb-admin-table-text truncate font-semibold text-fg-1">{user.name}</span>
            {isCurrentUser && (
              <span className="rounded-pill bg-surface-raised px-[7px] py-px text-[10px] font-bold text-fg-3">
                YOU
              </span>
            )}
          </span>
          <span className="pb-admin-table-meta block truncate text-fg-3">{user.email}</span>
        </span>
      </div>

      <div>
        <RoleBadge role={user.role} />
      </div>

      <div className="justify-self-start md:justify-self-end">
        {isCurrentUser ? (
          <span className="inline-flex items-center gap-1.5 text-xs text-fg-4">
            <Lock className="h-[13px] w-[13px]" />
            Locked
          </span>
        ) : (
          <RoleMenu currentRole={user.role} onChange={(role) => onRoleChange(user.id, role)} userName={user.name} />
        )}
      </div>
    </div>
  )
}

function RoleBadge({ role }: { role: UserRole }) {
  const meta = roleMeta[role]
  const RoleIcon = meta.icon

  return (
    <Badge className="px-3 py-1 text-xs" tone={meta.tone}>
      <RoleIcon className="h-3 w-3" />
      {meta.label}
    </Badge>
  )
}

interface RoleMenuProps {
  currentRole: UserRole
  onChange: (role: UserRole) => void
  userName: string
}

function RoleMenu({ currentRole, onChange, userName }: RoleMenuProps) {
  return (
    <DropdownMenuPrimitive.Root>
      <DropdownMenuPrimitive.Trigger asChild>
        <button
          aria-label={`Change role for ${userName}`}
          className="pb-admin-table-action"
          type="button"
        >
          Change role
          <ChevronDown className="pb-admin-table-action-icon" />
        </button>
      </DropdownMenuPrimitive.Trigger>
      <DropdownMenuPrimitive.Portal>
        <DropdownMenuPrimitive.Content
          align="end"
          className="pb-admin-menu"
          sideOffset={4}
        >
          {roleOptions.map((option) => {
            const selected = option.role === currentRole
            const meta = roleMeta[option.role]
            const RoleIcon = meta.icon

            return (
              <DropdownMenuPrimitive.Item
                className="pb-admin-menu-item"
                disabled={selected}
                key={option.role}
                onSelect={() => onChange(option.role)}
              >
                <RoleIcon className={cn('h-[15px] w-[15px] shrink-0', selected ? 'text-fg-4' : 'text-fg-3')} />
                {option.label}
                {selected && <Check className="ml-auto h-3.5 w-3.5 text-brand" />}
              </DropdownMenuPrimitive.Item>
            )
          })}
        </DropdownMenuPrimitive.Content>
      </DropdownMenuPrimitive.Portal>
    </DropdownMenuPrimitive.Root>
  )
}

function getInitials(name: string) {
  return (
    name
      .trim()
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase())
      .join('') || 'PB'
  )
}
