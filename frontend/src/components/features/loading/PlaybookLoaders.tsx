import type { ReactNode } from 'react'
import { Database, LayoutDashboard, Paperclip, Plus, RefreshCw, Search, Send, Sparkles, Users, Zap } from 'lucide-react'
import { AdminPageScaffold } from '@/src/components/features/admin/AdminPageScaffold'
import { AuthCard } from '@/src/components/features/auth/AuthLayout'
import { HorizonBackground } from '@/src/components/features/common/HorizonBackground'
import { WorkspaceShell } from '@/src/components/features/workspace/WorkspaceShell'
import { BrandLockup, Button, PlaybookMark, Skeleton, SkeletonAvatar, SkeletonButton, SkeletonText } from '@/src/components/ui'

type AdminSkeletonTab = 'insights' | 'kb' | 'users'

export function PlaybookRouteLoader() {
  return (
    <section className="pb-route-loader-stage">
      <div
        aria-label="Loading Playbook"
        className="pb-route-loader-content"
        data-testid="playbook-brand-loader"
        role="status"
      >
        <PlaybookMark className="pb-route-loader-mark" size={96} />
        <span className="pb-route-loader-text">Loading</span>
      </div>
    </section>
  )
}

export function AuthLoginSkeleton() {
  return (
    <AuthCard className="flex flex-col items-center text-center" data-testid="auth-loading-skeleton">
      <BrandLockup className="justify-center gap-[11px]" markSize={34} wordmarkClassName="pb-auth-wordmark" />
      <h1
        aria-label="Log in to continue"
        className="pb-auth-heading mt-6"
      >
        Log in to continue
      </h1>
      <div className="mt-8 grid w-full gap-3">
        {['microsoft', 'google'].map((provider) => (
          <AuthProviderSkeleton key={provider} />
        ))}
      </div>
      <footer className="pb-auth-footer mt-8 w-full border-t border-border pt-6">
        <span>Privacy Policy</span>
        <span className="px-2 text-fg-4">·</span>
        <span>Terms of Service</span>
      </footer>
    </AuthCard>
  )
}

export function ProfileCardSkeleton() {
  return (
    <AuthCard className="flex flex-col items-center text-center" data-testid="profile-card-skeleton">
      <BrandLockup className="justify-center gap-[11px]" markSize={34} wordmarkClassName="pb-auth-wordmark" />
      <h1 className="pb-auth-heading mt-6">
        Complete your profile
      </h1>
      <div className="pb-auth-profile-form">
        <div className="pb-auth-label pb-auth-profile-field">
          Name
          <div aria-hidden="true" className="pb-auth-profile-input" />
        </div>
        <div className="pb-auth-label pb-auth-profile-field">
          Sport or team
          <div aria-hidden="true" className="pb-auth-profile-input" />
        </div>
        <div aria-hidden="true" className="pb-auth-profile-submit pb-auth-profile-skeleton-submit">
          {"I'm ready"}
        </div>
      </div>
    </AuthCard>
  )
}

export function RootRedirectLoader() {
  return <PlaybookRouteLoader />
}

export function ChatWorkspaceSkeleton() {
  return (
    <WorkspaceShell
      leftRail={<ChatNavSkeleton />}
      main={<ChatMainSkeleton />}
    />
  )
}

export function ChatNavSkeleton() {
  return (
    <aside
      aria-label="Chat navigation loading"
      className="pb-workspace-chat-rail flex h-dvh shrink-0 flex-col border-r border-border bg-bg-void text-fg-1"
      data-testid="chat-workspace-skeleton"
    >
      <div className="flex items-center px-[18px] pb-3 pt-[18px]">
        <BrandLockup markSize={26} wordmarkClassName="pb-chat-brand-wordmark" className="gap-3" />
      </div>
      <div className="px-3 pb-2 pt-1">
        <button
          className="pb-focus-control pb-ui-sm flex h-[42px] w-full items-center gap-3 rounded-md border border-border-strong bg-transparent px-3 text-left font-semibold text-fg-1 transition"
          disabled
          type="button"
        >
          <Plus className="h-[17px] w-[17px] text-brand" />
          <span className="flex-1">New chat</span>
          <span className="pb-ui-xs text-fg-4">⌘N</span>
        </button>
      </div>
      <div className="px-3 pb-2">
        <label className="pb-field-shell pb-ui-sm flex h-[34px] items-center gap-2 rounded-md border border-border bg-surface px-2.5 text-fg-4">
          <Search className="h-[15px] w-[15px] shrink-0" />
          <span className="sr-only">Search chats</span>
          <input
            className="pb-ui-sm min-w-0 flex-1 border-0 bg-transparent text-fg-1 outline-none placeholder:text-fg-4"
            disabled
            placeholder="Search chats"
          />
        </label>
      </div>
      <ChatHistorySkeleton />
      <AccountBlockSkeleton />
    </aside>
  )
}

export function ChatHistorySkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <nav aria-label="Conversation history loading" className="flex-1 overflow-y-auto px-3 py-1">
      <div className="grid gap-1 pt-3">
        {Array.from({ length: rows }).map((_, index) => (
          <Skeleton
            className="h-[33px] rounded-sm"
            data-testid="chat-history-skeleton-row"
            key={index}
            style={{ width: `${86 - index * 7}%` }}
          />
        ))}
      </div>
    </nav>
  )
}

export function ChatMainSkeleton() {
  return (
    <section className="relative flex min-w-0 flex-1 flex-col overflow-hidden bg-bg-base" data-testid="chat-main-skeleton">
      <div className="pointer-events-none absolute inset-0" aria-hidden="true">
        <HorizonBackground />
      </div>
      <div className="relative z-10 flex min-h-0 flex-1 flex-col">
        <div className="pb-chat-thread" data-testid="chat-empty-skeleton">
          <div className="pb-chat-content flex w-full flex-col items-center gap-3 px-7 pb-4 pt-[13vh] text-center">
            <div className="flex items-center justify-center gap-3.5">
              <PlaybookMark className="pb-think text-fg-1" size={36} />
              <h1 className="pb-chat-empty-title">
                Ask PlaybookAI
              </h1>
            </div>
            <p className="pb-chat-body m-0 text-balance text-fg-3">
              Get answers to your athletics questions,
              <br />
              PlaybookAI is your coach off the field.
            </p>
          </div>
        </div>
        <div className="pb-chat-composer">
          <div className="pb-chat-content w-full">
            <div className="pb-chat-composer-shell pb-field-shell" data-testid="chat-composer-shell">
              <textarea
                aria-label="Message Playbook loading"
                className="pb-chat-composer-input px-1 pb-2.5 pt-1"
                disabled
                readOnly
                rows={1}
              />
              <div className="flex items-center gap-2.5">
                <button
                  aria-label="Attach file"
                  className="pb-focus-control inline-flex h-9 w-9 items-center justify-center rounded-sm border border-transparent text-fg-2 transition disabled:cursor-not-allowed disabled:text-fg-4"
                  disabled
                  type="button"
                >
                  <Paperclip className="h-[18px] w-[18px]" />
                </button>
                <Button className="ml-auto px-4" disabled size="sm" type="button">
                  Ask
                  <Send className="h-4 w-4" />
                </Button>
              </div>
            </div>
            <p className="pb-ui-xs mt-2.5 text-center text-fg-4">
              Responses are AI generated. Review to confirm accuracy.
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}

export function ChatThreadSkeleton({ label = 'Loading conversation' }: { label?: string }) {
  return (
    <div className="flex min-h-0 flex-1 justify-center overflow-y-auto py-7" data-testid="chat-thread-skeleton">
      <div className="pb-chat-content flex w-full flex-col gap-6 px-7">
        <p className="pb-refresh-note">
          <PlaybookMark className="pb-think text-brand" size={18} />
          {label}
        </p>
        <div className="flex justify-end">
          <Skeleton className="h-[78px] w-[58%] rounded-lg rounded-tr-sm" />
        </div>
        <div className="grid gap-3">
          <Skeleton className="h-3 w-[92px] rounded-pill" />
          <SkeletonText lines={4} widths={['92%', '100%', '84%', '62%']} />
        </div>
      </div>
    </div>
  )
}

interface AdminWorkspaceSkeletonProps {
  activeTab?: AdminSkeletonTab
  isSuperAdmin?: boolean
}

export function AdminWorkspaceSkeleton({
  activeTab = 'insights',
  isSuperAdmin = false,
}: AdminWorkspaceSkeletonProps = {}) {
  const safeActiveTab = activeTab === 'users' && !isSuperAdmin ? 'insights' : activeTab

  return (
    <WorkspaceShell
      leftRail={<AdminNavSkeleton activeTab={safeActiveTab} isSuperAdmin={isSuperAdmin} />}
      main={
        <section className="relative flex min-w-0 flex-1 flex-col overflow-hidden bg-bg-base" data-testid="admin-workspace-skeleton">
          <div className="admin-grid opacity-70" aria-hidden="true" />
          {safeActiveTab === 'users' && isSuperAdmin ? <AdminUsersPageSkeleton /> : <AdminInsightsSkeleton />}
        </section>
      }
    />
  )
}

interface AdminNavSkeletonProps {
  activeTab?: AdminSkeletonTab
  isSuperAdmin?: boolean
}

export function AdminNavSkeleton({
  activeTab = 'insights',
  isSuperAdmin = false,
}: AdminNavSkeletonProps = {}) {
  const safeActiveTab = activeTab === 'users' && !isSuperAdmin ? 'insights' : activeTab
  const navItems = [
    { icon: LayoutDashboard, id: 'insights', label: 'Insights' },
    { icon: Database, id: 'kb', label: 'Knowledge base' },
    ...(isSuperAdmin ? [{ icon: Users, id: 'users', label: 'Users & roles' }] : []),
  ] as Array<{ icon: typeof LayoutDashboard; id: AdminSkeletonTab; label: string }>

  return (
    <aside className="pb-workspace-admin-rail flex h-dvh shrink-0 flex-col border-r border-border bg-bg-void text-fg-1" aria-label="Admin sidebar loading">
      <div className="px-[18px] pb-4 pt-5">
        <BrandLockup className="gap-2.5" markSize={24} wordmarkClassName="pb-admin-brand-wordmark" />
        <span className="sr-only">Admin</span>
        <span className="pb-admin-sidebar-label float-right -mt-4">Admin</span>
      </div>
      <nav className="flex-1 px-3 py-0.5" aria-label="Admin navigation loading">
        {navItems.map((item) => {
          const Icon = item.icon
          const active = item.id === safeActiveTab
          return (
            <div
              className={`pb-focus-control pb-admin-nav-item relative mb-0.5 flex w-full items-center gap-2.5 rounded-sm border border-transparent px-[11px] py-2.5 font-medium ${active ? 'bg-brand-soft text-brand' : 'text-fg-2'}`}
              key={item.label}
            >
              {active && <span className="absolute left-0 top-1/2 h-4 w-[3px] -translate-y-1/2 rounded-r-sm bg-brand" />}
              <Icon className="pb-admin-nav-icon" />
              <span className="min-w-0 flex-1 truncate">{item.label}</span>
            </div>
          )
        })}
      </nav>
      <AccountBlockSkeleton />
    </aside>
  )
}

export function AdminInsightsSkeleton() {
  return (
    <div className="relative z-10 min-h-0 flex-1 overflow-y-auto" data-testid="admin-insights-skeleton">
      <AdminPageScaffold
        actions={
          <>
            <span className="pb-admin-header-control pb-ui-sm hidden items-center gap-2 rounded-md border border-border-strong bg-surface font-semibold text-fg-1 sm:inline-flex">
              Last 7 days
            </span>
            <span className="pb-admin-header-control pb-admin-insights-regenerate-control pb-ui-sm hidden items-center gap-2 rounded-md border border-border-strong bg-surface font-semibold text-fg-2 sm:inline-flex">
              <RefreshCw className="h-[15px] w-[15px]" />
              Regenerate
            </span>
            <span className="pb-admin-header-control pb-ui-sm hidden items-center gap-2 rounded-md border border-transparent bg-brand font-semibold text-fg-on-brand opacity-80 sm:inline-flex">
              <Zap className="h-[15px] w-[15px]" />
              Explore with AI
            </span>
          </>
        }
        subtitle="AI generated insights from user queries"
        title="Insights"
      >
        <section className="pb-dashboard-summary-card">
          <div className="mb-3 flex items-center gap-2.5">
            <span className="pb-dashboard-section-label inline-flex items-center gap-2 font-bold text-brand">
              <Sparkles className="h-4 w-4" />
              AI summary
            </span>
            <span className="pb-dashboard-meta ml-auto">Loading summary</span>
          </div>
          <SkeletonText lines={3} widths={['92%', '100%', '70%']} />
          <div className="mt-3.5 grid border-t border-border pt-3.5 md:grid-cols-3">
            {Array.from({ length: 3 }).map((_, index) => (
              <div className={index > 0 ? 'mt-4 border-t border-border pt-4 md:mt-0 md:border-l md:border-t-0 md:pl-6 md:pt-0' : ''} key={index}>
                <Skeleton className="h-7 w-16 rounded-sm" />
                <Skeleton className="mt-2 h-3 w-28 rounded-pill" />
              </div>
            ))}
          </div>
        </section>
        <div className="mt-3.5 grid items-stretch gap-4 lg:grid-cols-[1.55fr_1fr]">
          <AdminDashboardCardSkeleton title="Common topics">
            <TopicBarsSkeleton />
          </AdminDashboardCardSkeleton>
          <AdminDashboardCardSkeleton title="Risk flags">
            <RiskFlagsSkeleton />
          </AdminDashboardCardSkeleton>
        </div>
        <AdminDashboardCardSkeleton className="mt-3.5" title="Query volume">
          <QueryVolumeSkeleton />
        </AdminDashboardCardSkeleton>
        <AdminQueryReviewSkeleton />
      </AdminPageScaffold>
    </div>
  )
}

function AdminUsersPageSkeleton() {
  return (
    <div className="relative z-10 min-h-0 flex-1 overflow-y-auto" data-testid="admin-users-page-skeleton">
      <AdminPageScaffold
        contentClassName="py-[18px]"
        contentMaxWidthClassName="pb-admin-content-narrow"
        title="Users & roles"
      >
        <AdminUsersSkeleton />
      </AdminPageScaffold>
    </div>
  )
}

export function AdminKBSkeleton() {
  return (
    <div className="grid gap-4" data-testid="admin-kb-skeleton">
      <div className="pb-admin-kb-grid">
        {Array.from({ length: 4 }).map((_, index) => (
          <Skeleton className="h-[164px] rounded-lg border border-border-strong" data-testid="admin-kb-collection-skeleton" key={index} />
        ))}
      </div>
    </div>
  )
}

export function AdminUsersSkeleton() {
  return (
    <section aria-label="Users and roles loading" className="overflow-hidden rounded-lg border border-border-strong bg-surface" data-testid="admin-users-skeleton">
      <div className="border-b border-border bg-bg-base px-4 py-3">
        <div className="pb-admin-table-search pb-field-shell">
          <Search className="pb-admin-table-search-icon" />
          <span className="text-fg-4">Search users...</span>
        </div>
      </div>
      <div className="hidden grid-cols-[2fr_1.2fr_150px] gap-3.5 border-b border-border bg-bg-base px-4 py-[11px] md:grid">
        {['User', 'Role', ''].map((header) => (
          <span
            className="pb-admin-table-heading"
            key={header || 'actions'}
          >
            {header}
          </span>
        ))}
      </div>
      {Array.from({ length: 6 }).map((_, index) => (
        <div className="grid gap-3.5 border-b border-border px-4 py-[13px] last:border-b-0 md:grid-cols-[2fr_1.2fr_150px] md:items-center" key={index}>
          <div className="flex min-w-0 items-center gap-3">
            <SkeletonAvatar sizeClassName="h-[34px] w-[34px]" />
            <SkeletonText className="w-full max-w-[220px]" lines={2} widths={['78%', '100%']} />
          </div>
          <Skeleton className="h-6 w-[112px] rounded-pill" />
          <SkeletonButton className="h-[30px] w-[112px] justify-self-start md:justify-self-end" />
        </div>
      ))}
    </section>
  )
}

function AdminDashboardCardSkeleton({
  children,
  className,
  title,
}: {
  children: ReactNode
  className?: string
  title: string
}) {
  return (
    <section className={`pb-dashboard-card ${className ?? ''}`}>
      <div className="mb-3 flex items-center">
        <h2 className="pb-card-title">{title}</h2>
      </div>
      {children}
    </section>
  )
}

function TopicBarsSkeleton() {
  return (
    <div className="pb-dashboard-breakdown-scroll">
      <div className="grid gap-2.5">
        {Array.from({ length: 4 }).map((_, index) => (
          <div className="grid grid-cols-[92px_1fr_34px] items-center gap-3" key={index}>
            <Skeleton className="h-3 w-16 rounded-pill" />
            <Skeleton className="h-[9px] rounded-pill" />
            <Skeleton className="h-3 w-7 rounded-pill justify-self-end" />
          </div>
        ))}
      </div>
    </div>
  )
}

function RiskFlagsSkeleton() {
  return (
    <div className="pb-dashboard-breakdown-scroll">
      <div className="grid gap-0.5">
        {Array.from({ length: 3 }).map((_, index) => (
          <div className={`flex items-center gap-3 px-1 py-3.5 ${index < 2 ? 'border-b border-border' : ''}`} key={index}>
            <Skeleton className="h-2 w-2 shrink-0 rounded-full" />
            <Skeleton className="h-3 flex-1 rounded-pill" />
            <Skeleton className="h-4 w-14 rounded-pill" />
            <Skeleton className="h-5 w-8 rounded-sm" />
          </div>
        ))}
      </div>
    </div>
  )
}

function QueryVolumeSkeleton() {
  return (
    <div>
      <div className="flex h-[116px] items-end gap-3 px-0.5">
        {[64, 82, 94, 50, 70, 100, 76].map((height, index) => (
          <div className="flex flex-1 flex-col items-center gap-2" key={index}>
            <Skeleton className="w-full max-w-10 rounded-t" style={{ height }} />
            <Skeleton className="h-3 w-6 rounded-pill" />
          </div>
        ))}
      </div>
      <div className="mt-2.5 flex items-center gap-4 border-t border-border pt-2.5">
        <Skeleton className="h-3 w-20 rounded-pill" />
        <Skeleton className="h-3 w-32 rounded-pill" />
        <Skeleton className="ml-auto h-3 w-20 rounded-pill" />
      </div>
    </div>
  )
}

function AdminQueryReviewSkeleton() {
  return (
    <section aria-labelledby="admin-query-review-skeleton-title" className="pb-dashboard-card mt-3.5">
      <div className="mb-3 flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <h2 className="pb-card-title" id="admin-query-review-skeleton-title">Query review</h2>
          <p className="pb-dashboard-meta mt-1 text-fg-3">
            Anonymized athlete questions in the selected window.
          </p>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <span className="pb-dashboard-section-label mr-1 text-fg-3">Topics</span>
        {Array.from({ length: 4 }).map((_, index) => (
          <Skeleton className="h-[24px] w-20 rounded-pill" key={index} />
        ))}
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <span className="pb-dashboard-section-label mr-1 text-fg-3">Risks</span>
        {Array.from({ length: 3 }).map((_, index) => (
          <Skeleton className="h-[24px] w-24 rounded-pill" key={index} />
        ))}
      </div>
      <div className="mt-4 overflow-hidden rounded-md border border-border">
        {Array.from({ length: 3 }).map((_, index) => (
          <div className={`bg-bg-base px-3 py-3 ${index < 2 ? 'border-b border-border' : ''}`} key={index}>
            <div className="flex items-start gap-3">
              <Skeleton className="mt-0.5 h-4 w-4 shrink-0 rounded-sm" />
              <div className="min-w-0 flex-1">
                <Skeleton className="h-3.5 w-[82%] rounded-pill" />
                <Skeleton className="mt-2 h-3 w-[48%] rounded-pill" />
              </div>
            </div>
          </div>
        ))}
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <Skeleton className="h-3 w-16 rounded-pill" />
        <div className="ml-auto flex items-center gap-2">
          <SkeletonButton className="h-8 w-[86px]" />
          <span className="pb-dashboard-meta min-w-12 text-center text-fg-3">Page 1</span>
          <SkeletonButton className="h-8 w-[62px]" />
        </div>
      </div>
    </section>
  )
}

function AuthProviderSkeleton() {
  return (
    <div
      aria-hidden="true"
      className="pb-auth-provider-button"
      data-testid="auth-provider-skeleton"
    >
      <span className="pb-auth-provider-icon">
        <Skeleton className="h-5 w-5 rounded-sm" />
      </span>
      <span className="pb-auth-provider-label">
        <Skeleton className="h-4 w-[190px] max-w-[80%] rounded-sm" />
      </span>
    </div>
  )
}

function AccountBlockSkeleton() {
  return (
    <div className="border-t border-border px-3 py-3.5">
      <div className="flex w-full items-center gap-2.5 rounded-md px-2.5 py-2">
        <SkeletonAvatar />
        <SkeletonText className="min-w-0 flex-1" lines={2} widths={['72%', '54%']} />
      </div>
    </div>
  )
}
