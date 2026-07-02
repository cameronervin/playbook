'use client'

import { type ReactNode, useMemo, useState } from 'react'
import Link from 'next/link'
import * as DropdownMenuPrimitive from '@radix-ui/react-dropdown-menu'
import { ChevronsUpDown, FileText, LayoutDashboard, LogOut, Plus, ScrollText, Search, Settings, X } from 'lucide-react'
import { ChatHistorySkeleton } from '@/src/components/features/loading/PlaybookLoaders'
import { BrandLockup } from '@/src/components/ui'
import { ROUTES } from '@/src/lib/constants/config'
import { isAdminRole } from '@/src/lib/authRouting'
import { cn } from '@/src/lib/utils/cn'
import type { CurrentUser } from '@/src/types/auth'
import type { ConversationSummary } from '@/src/types/conversations'
import type { ConversationGroup } from './chatTypes'

interface ChatNavRailProps {
  activeConversationId: string | null
  groups: ConversationGroup[]
  isFetching?: boolean
  isLoading?: boolean
  isLoggingOut: boolean
  onLogout: () => void
  onNewChat: () => void
  onOpenSettings: () => void
  onSelectConversation: (conversationId: string) => void
  user?: CurrentUser
}

const ACCOUNT_LEGAL_LINKS: Array<{ href: string; icon: ReactNode; label: string }> = [
  { href: ROUTES.privacy, icon: <FileText className="h-4 w-4" />, label: 'Privacy Policy' },
  { href: ROUTES.terms, icon: <ScrollText className="h-4 w-4" />, label: 'Terms of Service' },
]

export function ChatNavRail({
  activeConversationId,
  groups,
  isFetching = false,
  isLoading = false,
  isLoggingOut,
  onLogout,
  onNewChat,
  onOpenSettings,
  onSelectConversation,
  user,
}: ChatNavRailProps) {
  const [query, setQuery] = useState('')
  const normalizedQuery = query.trim().toLowerCase()
  const visibleGroups = useMemo(
    () =>
      groups
        .map((group) => ({
          ...group,
          conversations: group.conversations.filter((conversation) =>
            getConversationTitle(conversation).toLowerCase().includes(normalizedQuery),
          ),
        }))
        .filter((group) => group.conversations.length > 0),
    [groups, normalizedQuery],
  )
  const showActiveNewChat = !activeConversationId && (!normalizedQuery || 'new chat'.includes(normalizedQuery))
  const initials = getInitials(user?.name)
  const teamLabel = user?.sport_team ?? 'Athletics Department'
  const isAdmin = user ? isAdminRole(user.role) : false

  return (
    <aside
      className="pb-workspace-chat-rail flex h-dvh shrink-0 flex-col border-r border-border bg-bg-void text-fg-1"
      aria-label="Chat navigation"
    >
      <div className="flex items-center px-[18px] pb-3 pt-[18px]">
        <BrandLockup
          markSize={26}
          wordmarkClassName="pb-chat-brand-wordmark"
          className="gap-3"
        />
      </div>

      <div className="px-3 pb-2 pt-1">
        <button
          className="pb-focus-control pb-ui-sm flex h-[42px] w-full items-center gap-3 rounded-md border border-border-strong bg-transparent px-3 text-left font-semibold text-fg-1 transition hover:bg-surface-hover active:translate-y-px"
          onClick={onNewChat}
          type="button"
        >
          <Plus className="h-[17px] w-[17px] text-brand" />
          <span className="flex-1">New chat</span>
        </button>
      </div>

      <div className="px-3 pb-2">
        <label className="pb-field-shell pb-ui-sm flex h-[34px] items-center gap-2 rounded-md border border-border bg-surface px-2.5 text-fg-4">
          <Search className="h-[15px] w-[15px] shrink-0" />
          <span className="sr-only">Search chats</span>
          <input
            className="pb-ui-sm min-w-0 flex-1 border-0 bg-transparent text-fg-1 outline-none placeholder:text-fg-4"
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search chats"
            value={query}
          />
          {query && (
            <button
              aria-label="Clear chat search"
              className="pb-focus-control rounded-sm border border-transparent text-fg-4 transition hover:text-fg-2"
              onClick={() => setQuery('')}
              type="button"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </label>
      </div>

      {isLoading ? (
        <ChatHistorySkeleton />
      ) : (
        <nav className="flex-1 overflow-y-auto px-3 py-1" aria-label="Conversation history">
          {isFetching && (
            <p className="pb-refresh-note px-[11px] py-2">
              <span className="pb-spin h-2 w-2 rounded-full border border-info border-t-transparent" />
              Refreshing chats
            </p>
          )}
          {visibleGroups.length === 0 && !showActiveNewChat ? (
            <p className="pb-ui-sm px-[11px] py-[18px] text-fg-4">No matching chats.</p>
          ) : (
            <>
              {(showActiveNewChat || visibleGroups.some((group) => group.label === 'Today')) && (
                <HistoryGroupLabel label="Today" />
              )}
              {showActiveNewChat && (
                <ConversationRow active title="New chat" onClick={onNewChat} />
              )}
              {visibleGroups.map((group) => (
                <div key={group.label}>
                  {group.label !== 'Today' && <HistoryGroupLabel label={group.label} />}
                  {group.conversations.map((conversation) => (
                    <ConversationRow
                      active={activeConversationId === conversation.id}
                      key={conversation.id}
                      onClick={() => onSelectConversation(conversation.id)}
                      title={getConversationTitle(conversation)}
                    />
                  ))}
                </div>
              ))}
            </>
          )}
        </nav>
      )}

      <div className="border-t border-border px-3 py-3.5">
        <DropdownMenuPrimitive.Root>
          <DropdownMenuPrimitive.Trigger asChild>
            <button
              className="pb-focus-control flex w-full items-center gap-2.5 rounded-md border border-transparent px-2.5 py-2 text-left transition hover:border-border-strong hover:bg-surface-hover data-[state=open]:border-border-strong data-[state=open]:bg-surface-hover"
              type="button"
              aria-label={`${user?.name ?? 'Playbook user'} account menu`}
            >
              <span className="relative shrink-0">
                <span className="pb-ui-sm flex h-8 w-8 items-center justify-center rounded-md bg-brand font-display font-extrabold text-fg-on-brand">
                  {initials}
                </span>
                <span className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-bg-void bg-success" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="pb-ui-sm block truncate font-semibold text-fg-1">{user?.name ?? 'Playbook user'}</span>
                <span className="pb-ui-xs block truncate text-fg-3">{teamLabel}</span>
              </span>
              <ChevronsUpDown className="h-4 w-4 shrink-0 text-fg-4" />
            </button>
          </DropdownMenuPrimitive.Trigger>
          <DropdownMenuPrimitive.Portal>
            <DropdownMenuPrimitive.Content
              align="start"
              className="pb-menu-content pb-ui-sm"
              side="top"
              sideOffset={8}
            >
              <div className="flex items-center gap-3 border-b border-border px-2 py-2.5">
                <span className="pb-ui-sm flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-brand font-display font-extrabold text-fg-on-brand">
                  {initials}
                </span>
                <span className="min-w-0">
                  <span className="pb-ui-sm block truncate font-bold text-fg-1">{user?.name ?? 'Playbook user'}</span>
                  <span className="pb-ui-xs block truncate text-fg-3">{user?.email ?? 'Signed in with SSO'}</span>
                </span>
              </div>
              <DropdownItem icon={<Settings className="h-4 w-4" />} onSelect={onOpenSettings}>
                Settings
              </DropdownItem>
              {isAdmin && (
                <DropdownLinkItem href={ROUTES.admin} icon={<LayoutDashboard className="h-4 w-4" />}>
                  Admin dashboard
                </DropdownLinkItem>
              )}
              <div className="mt-1 border-t border-border pt-1">
                {ACCOUNT_LEGAL_LINKS.map((link) => (
                  <DropdownLinkItem href={link.href} icon={link.icon} key={link.href}>
                    {link.label}
                  </DropdownLinkItem>
                ))}
              </div>
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

interface ConversationRowProps {
  active: boolean
  onClick: () => void
  title: string
}

function ConversationRow({ active, onClick, title }: ConversationRowProps) {
  return (
    <button
      className={cn(
        'pb-focus-control pb-ui-sm relative mb-px flex w-full items-center rounded-sm border border-transparent px-[11px] py-2 text-left font-medium text-fg-2 transition hover:bg-surface-hover hover:text-fg-1',
        active && 'bg-brand-soft font-semibold text-brand hover:bg-brand-soft hover:text-brand',
      )}
      onClick={onClick}
      type="button"
    >
      {active && <span className="absolute left-0 top-1/2 h-[15px] w-[3px] -translate-y-1/2 rounded-r-sm bg-brand" />}
      <span className="truncate">{title}</span>
    </button>
  )
}

function HistoryGroupLabel({ label }: { label: ConversationGroup['label'] }) {
  return <p className="pb-ui-xs px-[11px] pb-1.5 pt-3 font-semibold text-fg-3">{label}</p>
}

interface DropdownLinkItemProps {
  children: ReactNode
  href: string
  icon: ReactNode
}

function DropdownLinkItem({ children, href, icon }: DropdownLinkItemProps) {
  return (
    <DropdownMenuPrimitive.Item asChild>
      <Link
        className="pb-focus-item pb-ui-sm mt-1 flex cursor-pointer items-center gap-2.5 rounded-sm px-2.5 py-2 font-medium text-fg-2 transition"
        href={href}
      >
        <span className="text-fg-3">{icon}</span>
        {children}
      </Link>
    </DropdownMenuPrimitive.Item>
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
        'pb-focus-item pb-ui-sm mt-1 flex cursor-pointer items-center gap-2.5 rounded-sm px-2.5 py-2 font-medium transition data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
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

function getConversationTitle(conversation: ConversationSummary) {
  return conversation.title?.trim() || 'New chat'
}

function getInitials(name?: string) {
  if (!name) return 'PB'
  const parts = name.trim().split(/\s+/).filter(Boolean)
  return parts
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('') || 'PB'
}
