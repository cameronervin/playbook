'use client'

import { type ReactNode } from 'react'
import * as DropdownMenuPrimitive from '@radix-ui/react-dropdown-menu'
import { ChevronsUpDown, Database, LayoutDashboard, LogOut, MessageCircle, Settings, Users } from 'lucide-react'
import { BrandLockup } from '@/src/components/ui'
import { cn } from '@/src/lib/utils/cn'
import type { CurrentUser } from '@/src/types/auth'

type AdminTab = 'insights' | 'kb' | 'users'

interface AdminNavProps {
  activeTab: AdminTab
  failedDocsCount: number
  isLoggingOut: boolean
  isSuperAdmin: boolean
  onLogout: () => void
  onNavigate: (tab: AdminTab) => void
  onOpenChatWorkspace: () => void
  onOpenSettings: () => void
  user?: CurrentUser
}

const navItems: Array<{ id: AdminTab; icon: ReactNode; label: string }> = [
  { id: 'insights', icon: <LayoutDashboard className="pb-admin-nav-icon" />, label: 'Insights' },
  { id: 'kb', icon: <Database className="pb-admin-nav-icon" />, label: 'Knowledge base' },
  { id: 'users', icon: <Users className="pb-admin-nav-icon" />, label: 'Users & roles' },
]

export function AdminNav({
  activeTab,
  failedDocsCount,
  isLoggingOut,
  isSuperAdmin,
  onLogout,
  onNavigate,
  onOpenChatWorkspace,
  onOpenSettings,
  user,
}: AdminNavProps) {
  const initials = getInitials(user?.name)
  const roleLabel = isSuperAdmin ? 'Super admin' : 'Department admin'
  const visibleItems = navItems.filter((item) => item.id !== 'users' || isSuperAdmin)

  return (
    <aside className="pb-workspace-admin-rail flex h-dvh shrink-0 flex-col border-r border-border bg-bg-void text-fg-1" aria-label="Admin sidebar">
      <div className="px-[18px] pb-4 pt-5">
        <BrandLockup
          className="gap-2.5"
          markSize={24}
          wordmarkClassName="pb-admin-brand-wordmark"
        />
        <span className="sr-only">Admin</span>
        <span className="pb-admin-sidebar-label float-right -mt-4">Admin</span>
      </div>
      <nav className="flex-1 overflow-y-auto px-3 py-0.5" aria-label="Admin navigation">
        {visibleItems.map((item) => (
          <button
            aria-label={getNavLabel(item.id, item.label, failedDocsCount)}
            className={cn(
              'pb-focus-control pb-admin-nav-item relative mb-0.5 flex w-full items-center gap-2.5 rounded-sm border border-transparent px-[11px] py-2.5 text-left font-medium text-fg-2 transition hover:bg-surface-hover hover:text-fg-1',
              activeTab === item.id && 'bg-brand-soft font-semibold text-brand hover:bg-brand-soft hover:text-brand',
            )}
            key={item.id}
            onClick={() => onNavigate(item.id)}
            type="button"
          >
            {activeTab === item.id && <span className="absolute left-0 top-1/2 h-4 w-[3px] -translate-y-1/2 rounded-r-sm bg-brand" />}
            {item.icon}
            <span className="min-w-0 flex-1 truncate">{item.label}</span>
            {item.id === 'kb' && failedDocsCount > 0 && (
              <span className="pb-admin-small-badge bg-danger-bg text-danger">
                {failedDocsCount}
              </span>
            )}
          </button>
        ))}
      </nav>
      <div className="border-t border-border px-3 py-3.5">
        <DropdownMenuPrimitive.Root>
          <DropdownMenuPrimitive.Trigger asChild>
            <button
              aria-label={`${user?.name ?? 'Admin user'} account menu`}
              className="pb-focus-control flex w-full items-center gap-2.5 rounded-md border border-transparent px-2.5 py-2 text-left transition hover:border-border-strong hover:bg-surface-hover data-[state=open]:border-border-strong data-[state=open]:bg-surface-hover"
              type="button"
            >
              <span className="relative shrink-0">
                <span className="pb-admin-avatar pb-admin-avatar-sm bg-brand text-fg-on-brand">
                  {initials}
                </span>
                <span className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-bg-void bg-success" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="pb-admin-account-name block truncate">{user?.name ?? 'Playbook admin'}</span>
                <span className="pb-admin-account-meta block truncate">{roleLabel}</span>
              </span>
              <ChevronsUpDown className="h-4 w-4 shrink-0 text-fg-4" />
            </button>
          </DropdownMenuPrimitive.Trigger>
          <DropdownMenuPrimitive.Portal>
            <DropdownMenuPrimitive.Content
              align="start"
              className="pb-admin-menu-content"
              side="top"
              sideOffset={8}
            >
              <DropdownItem icon={<Settings className="h-4 w-4" />} onSelect={onOpenSettings}>
                Settings
              </DropdownItem>
              <DropdownItem icon={<MessageCircle className="h-4 w-4" />} onSelect={onOpenChatWorkspace}>
                Chat workspace
              </DropdownItem>
              <div className="mt-1 border-t border-border pt-1">
                <DropdownItem danger disabled={isLoggingOut} icon={<LogOut className="h-4 w-4" />} onSelect={onLogout}>
                  Sign out
                </DropdownItem>
              </div>
            </DropdownMenuPrimitive.Content>
          </DropdownMenuPrimitive.Portal>
        </DropdownMenuPrimitive.Root>
      </div>
    </aside>
  )
}

interface DropdownItemProps {
  children: ReactNode
  danger?: boolean
  disabled?: boolean
  icon: ReactNode
  onSelect: () => void
}

function DropdownItem({ children, danger = false, disabled = false, icon, onSelect }: DropdownItemProps) {
  return (
    <DropdownMenuPrimitive.Item
      className={cn(
        'pb-focus-item mt-1 flex cursor-pointer items-center gap-2.5 rounded-sm px-2.5 py-2 pb-ui-sm font-medium transition data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
        danger ? 'text-danger focus:bg-danger-bg focus:text-danger' : 'text-fg-2',
      )}
      disabled={disabled}
      onSelect={onSelect}
    >
      <span className={cn('text-fg-3', danger && 'text-danger')}>{icon}</span>
      {children}
    </DropdownMenuPrimitive.Item>
  )
}

function getNavLabel(id: AdminTab, label: string, failedDocsCount: number) {
  if (id === 'kb' && failedDocsCount > 0) {
    return `${label} ${failedDocsCount} failed ${failedDocsCount === 1 ? 'document' : 'documents'}`
  }
  return label
}

function getInitials(name?: string) {
  if (!name) return 'PB'
  return (
    name
      .trim()
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase())
      .join('') || 'PB'
  )
}
