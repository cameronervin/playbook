import { Database, LayoutDashboard, Paperclip, Plus, RefreshCw, Search, Send, Sparkles, Zap } from 'lucide-react'
import { AuthCard } from '@/src/components/features/auth/AuthLayout'
import { HorizonBackground } from '@/src/components/features/common/HorizonBackground'
import { WorkspaceShell } from '@/src/components/features/workspace/WorkspaceShell'
import { BrandLockup, Button, PlaybookMark, Skeleton, SkeletonAvatar, SkeletonButton, SkeletonText } from '@/src/components/ui'

export function AuthLoginSkeleton() {
  return (
    <AuthCard className="flex flex-col items-center text-center" data-testid="auth-loading-skeleton">
      <BrandLockup className="justify-center gap-[11px]" markSize={34} wordmarkClassName="text-[26px] leading-none tracking-normal" />
      <h1
        aria-label="Log in to continue"
        className="mt-6 font-display text-lg font-bold uppercase leading-[1.2] tracking-normal text-fg-1"
      >
        LOG IN TO CONTINUE
      </h1>
      <div className="mt-8 grid w-full gap-3">
        {['microsoft', 'google'].map((provider) => (
          <AuthProviderSkeleton key={provider} />
        ))}
      </div>
      <footer className="mt-8 w-full border-t border-border pt-6 text-xs text-fg-3">
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
      <BrandLockup className="justify-center gap-[11px]" markSize={34} wordmarkClassName="text-[26px] leading-none tracking-normal" />
      <h1 className="mt-6 font-display text-lg font-bold leading-[1.2] tracking-normal text-fg-1">
        Complete your profile
      </h1>
      <div className="mt-7 grid w-full gap-5 text-left">
        <div className="grid gap-2 text-sm font-semibold text-fg-2">
          Name
          <div aria-hidden="true" className="h-[52px] w-full rounded-md border border-border-strong bg-surface" />
        </div>
        <div className="grid gap-2 text-sm font-semibold text-fg-2">
          Sport or team
          <div aria-hidden="true" className="h-[52px] w-full rounded-md border border-border-strong bg-surface" />
        </div>
        <div aria-hidden="true" className="inline-flex min-h-[52px] w-full items-center justify-center rounded-md bg-brand px-4 text-base font-semibold text-fg-on-brand opacity-70">
          {"I'm ready"}
        </div>
      </div>
    </AuthCard>
  )
}

export function RootRedirectLoader() {
  return (
    <main className="pb-stage flex min-h-dvh items-center justify-center p-6" data-testid="root-redirect-loader">
      <div className="flex flex-col items-center gap-4 text-center">
        <BrandLockup />
        <span className="pb-refresh-note">
          <PlaybookMark className="pb-think text-brand" size={18} />
          Opening Playbook
        </span>
      </div>
    </main>
  )
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
      className="flex h-dvh w-[264px] shrink-0 flex-col border-r border-border bg-bg-void text-fg-1"
      data-testid="chat-workspace-skeleton"
    >
      <div className="flex items-center px-[18px] pb-3 pt-[18px]">
        <BrandLockup markSize={26} wordmarkClassName="font-black uppercase tracking-normal text-[20px]" className="gap-3" />
      </div>
      <div className="px-3 pb-2 pt-1">
        <button
          className="pb-ui-sm flex h-[42px] w-full items-center gap-3 rounded-md border border-border-strong bg-transparent px-3 text-left font-semibold text-fg-1 transition"
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
        <div className="flex min-h-0 flex-1 justify-center overflow-y-auto py-7" data-testid="chat-empty-skeleton">
          <div className="flex w-full max-w-[760px] flex-col items-center gap-3 px-7 pb-4 pt-[13vh] text-center">
            <div className="flex items-center justify-center gap-3.5">
              <PlaybookMark className="pb-think text-fg-1" size={36} />
              <h1 className="m-0 font-display text-[30px] font-extrabold leading-none tracking-normal text-fg-1 sm:text-[34px]">
                Ask PlaybookAI
              </h1>
            </div>
            <p className="m-0 text-balance text-sm leading-6 text-fg-3">
              Get answers to your athletics questions,
              <br />
              PlaybookAI is your coach off the field.
            </p>
          </div>
        </div>
        <div className="flex shrink-0 justify-center bg-bg-base px-7 pb-[22px] pt-3.5">
          <div className="w-full max-w-[760px]">
            <div className="pb-field-shell rounded-lg border border-border-solid bg-surface p-3 shadow-sm" data-testid="chat-composer-shell">
              <textarea
                aria-label="Message Playbook loading"
                className="min-h-[48px] w-full resize-none border-0 bg-transparent px-1 pb-2.5 pt-1 text-sm leading-6 text-fg-1 outline-none placeholder:text-fg-4"
                disabled
                readOnly
                rows={1}
              />
              <div className="flex items-center gap-2.5">
                <button
                  aria-label="Attach file"
                  className="inline-flex h-9 w-9 items-center justify-center rounded-sm text-fg-2 transition disabled:cursor-not-allowed disabled:text-fg-4"
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
      <div className="flex w-full max-w-[760px] flex-col gap-6 px-7">
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

export function AdminWorkspaceSkeleton() {
  return (
    <WorkspaceShell
      leftRail={<AdminNavSkeleton />}
      main={
        <section className="relative flex min-w-0 flex-1 flex-col overflow-hidden bg-bg-base" data-testid="admin-workspace-skeleton">
          <div className="admin-grid opacity-70" aria-hidden="true" />
          <AdminInsightsSkeleton />
        </section>
      }
    />
  )
}

export function AdminNavSkeleton() {
  const navItems = [
    { icon: LayoutDashboard, label: 'Insights', active: true },
    { icon: Database, label: 'Knowledge base', active: false },
  ]

  return (
    <aside className="flex h-dvh w-[244px] shrink-0 flex-col border-r border-border bg-bg-void text-fg-1" aria-label="Admin sidebar loading">
      <div className="px-[18px] pb-4 pt-5">
        <BrandLockup className="gap-2.5" markSize={24} wordmarkClassName="text-[19px] font-black uppercase leading-none tracking-normal" />
        <span className="sr-only">Admin</span>
        <span className="float-right -mt-4 text-[10.5px] font-bold uppercase tracking-[0.08em] text-fg-3">Admin</span>
      </div>
      <nav className="flex-1 px-3 py-0.5" aria-label="Admin navigation loading">
        {navItems.map((item) => {
          const Icon = item.icon
          return (
            <div
              className={`pb-admin-nav-item relative mb-0.5 flex w-full items-center gap-2.5 rounded-sm px-[11px] py-2.5 font-medium ${item.active ? 'bg-brand-soft text-brand' : 'text-fg-2'}`}
              key={item.label}
            >
              {item.active && <span className="absolute left-0 top-1/2 h-4 w-[3px] -translate-y-1/2 rounded-r-sm bg-brand" />}
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
      <header className="relative shrink-0 border-b border-border bg-bg-base px-7">
        <div className="admin-grid" aria-hidden="true" />
        <div className="relative z-10 flex min-h-[68px] items-center gap-5">
          <div className="min-w-0 flex-1">
            <h1 className="pb-page-title">Insights</h1>
          </div>
          <span className="pb-admin-header-control pb-ui-sm hidden items-center gap-2 rounded-md border border-border-strong bg-surface px-3 font-semibold text-fg-1 sm:inline-flex">
            Last 7 days
          </span>
          <span className="pb-admin-header-control pb-ui-sm hidden items-center gap-2 rounded-md border border-border-strong bg-surface px-3 font-semibold text-fg-2 sm:inline-flex">
            <RefreshCw className="h-[15px] w-[15px]" />
            Regenerate
          </span>
          <span className="pb-admin-header-control pb-ui-sm hidden items-center gap-2 rounded-md bg-brand px-3 font-semibold text-fg-on-brand opacity-80 sm:inline-flex">
            <Zap className="h-[15px] w-[15px]" />
            Explore with AI
          </span>
        </div>
      </header>
      <div className="px-7 py-4">
        <div className="mx-auto w-full max-w-[1000px]">
          <section className="rounded-lg border border-border-brand bg-[linear-gradient(180deg,rgba(255,115,0,0.06),transparent_52%),var(--surface)] p-[18px]">
            <div className="mb-3 flex items-center gap-2.5">
              <span className="inline-flex items-center gap-2 text-xs font-bold text-brand">
                <Sparkles className="h-4 w-4" />
                AI summary
              </span>
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
          <div className="mt-3.5 grid gap-4 lg:grid-cols-[1.55fr_1fr]">
            <AdminDashboardCardSkeleton title="Common topics" />
            <AdminDashboardCardSkeleton title="Risk flags" />
          </div>
          <AdminDashboardCardSkeleton className="mt-3.5" title="Query volume" />
        </div>
      </div>
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
            className="text-[10.5px] font-bold uppercase tracking-[0.06em] text-fg-4"
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

function AdminDashboardCardSkeleton({ className, title }: { className?: string; title: string }) {
  return (
    <section className={`rounded-lg border border-border-strong bg-surface p-[18px] ${className ?? ''}`}>
      <div className="mb-3 flex items-baseline">
        <h2 className="pb-card-title">{title}</h2>
      </div>
      <Skeleton className="h-[116px] rounded-md" />
    </section>
  )
}

function AuthProviderSkeleton() {
  return (
    <div
      aria-hidden="true"
      className="grid min-h-[52px] w-full grid-cols-[50px_1fr] overflow-hidden rounded-md border border-border-strong bg-surface"
      data-testid="auth-provider-skeleton"
    >
      <span className="flex items-center justify-center border-r border-border bg-surface-raised">
        <Skeleton className="h-5 w-5 rounded-sm" />
      </span>
      <span className="flex items-center justify-center py-[15px] pr-[50px] text-center">
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
