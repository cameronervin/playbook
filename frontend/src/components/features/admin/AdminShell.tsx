'use client'

import { useRouter } from 'next/navigation'
import { BarChart3, BookOpen, Lock, MessageCircle, RefreshCw, Settings, Shield, Trash2, Users } from 'lucide-react'
import { SettingsModal } from '@/src/components/features/common/SettingsModal'
import { Badge, BrandLockup, Button, IconButton, Surface } from '@/src/components/ui'
import { useAdminUsers, useAuditLogs, useUpdateUserRole } from '@/src/hooks/useAdmin'
import { useCurrentUser, useLogout } from '@/src/hooks/useAuth'
import {
  useDeleteKBDocument,
  useKBDocuments,
  useRetryKBDocument,
  useUpdateKBDocumentMetadata,
} from '@/src/hooks/useKBDocuments'
import { ANALYTICS_SUMMARY, DASHBOARD_INSIGHT } from '@/src/lib/fixtures/admin'
import { ROUTES } from '@/src/lib/constants/config'
import { useUIStore } from '@/src/lib/store/uiStore'
import { cn } from '@/src/lib/utils/cn'

export function AdminShell() {
  const router = useRouter()
  const { data: user, isLoading } = useCurrentUser()
  const logout = useLogout()
  const adminTab = useUIStore((state) => state.adminTab)
  const setAdminTab = useUIStore((state) => state.setAdminTab)
  const settingsOpen = useUIStore((state) => state.settingsOpen)
  const setSettingsOpen = useUIStore((state) => state.setSettingsOpen)
  const isSuperAdmin = user?.role === 'super_admin'
  const isAdmin = user?.role === 'admin' || isSuperAdmin
  const { data: documents = [] } = useKBDocuments()
  const { data: users = [] } = useAdminUsers(Boolean(isSuperAdmin))
  const { data: auditLogs = [] } = useAuditLogs(Boolean(isSuperAdmin))
  const retryDocument = useRetryKBDocument()
  const deleteDocument = useDeleteKBDocument()
  const updateDocument = useUpdateKBDocumentMetadata()
  const updateRole = useUpdateUserRole()

  if (isLoading) {
    return <main className="pb-stage flex min-h-dvh items-center justify-center text-sm text-fg-3">Loading admin...</main>
  }

  if (!isAdmin) {
    return (
      <main className="pb-stage flex min-h-dvh items-center justify-center p-6 text-center">
        <div className="max-w-md">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-lg border border-border-strong bg-surface">
            <Lock className="h-7 w-7 text-fg-3" />
          </div>
          <h1 className="mt-5 font-display text-3xl font-black uppercase text-fg-1">Admins only</h1>
          <p className="mt-3 text-sm leading-6 text-fg-3">
            The admin console is restricted to department admins. Your account does not have access to
            insights, analytics, or knowledge-base management.
          </p>
          <Button className="mt-5" onClick={() => router.push(ROUTES.chat)} variant="secondary">
            Back to chat workspace
          </Button>
        </div>
      </main>
    )
  }

  const handleLogout = async () => {
    await logout.mutateAsync()
    router.push(ROUTES.login)
  }

  return (
    <main className="grid min-h-dvh grid-cols-[272px_minmax(0,1fr)] bg-bg-base text-fg-1">
      <aside className="flex min-h-dvh flex-col border-r border-border bg-bg-page p-4">
        <BrandLockup markSize={28} />
        <nav className="mt-8 grid gap-2" aria-label="Admin navigation">
          <AdminNavButton active={adminTab === 'insights'} icon={<BarChart3 />} label="Insights" onClick={() => setAdminTab('insights')} />
          <AdminNavButton active={adminTab === 'kb'} icon={<BookOpen />} label="Knowledge base" onClick={() => setAdminTab('kb')} />
          {isSuperAdmin && (
            <AdminNavButton active={adminTab === 'users'} icon={<Users />} label="Users & roles" onClick={() => setAdminTab('users')} />
          )}
        </nav>
        <div className="mt-auto rounded-md border border-border-strong bg-surface p-3">
          <p className="text-sm font-semibold text-fg-1">{user?.name}</p>
          <p className="text-xs text-fg-4">{isSuperAdmin ? 'Super admin' : 'Department admin'}</p>
          <div className="mt-3 flex gap-2">
            <IconButton aria-label="Open settings" onClick={() => setSettingsOpen(true)}>
              <Settings className="h-4 w-4" />
            </IconButton>
            <Button className="flex-1" onClick={handleLogout} variant="secondary">
              Sign out
            </Button>
          </div>
        </div>
      </aside>

      <section className="relative overflow-auto p-6">
        <div className="pb-ambient-grid pointer-events-none absolute inset-0 opacity-40" />
        <div className="relative z-10">
          {adminTab === 'insights' && <InsightsPanel />}
          {adminTab === 'kb' && (
            <KBPanel
              canManage={isSuperAdmin}
              documents={documents}
              onDelete={(id) => deleteDocument.mutate(id)}
              onRetry={(id) => retryDocument.mutate(id)}
              onToggleOfficial={(id, isOfficial) => updateDocument.mutate({ documentId: id, isOfficial })}
            />
          )}
          {adminTab === 'users' && isSuperAdmin && (
            <UsersPanel
              auditCount={auditLogs.length}
              onRoleChange={(id, role) => updateRole.mutate({ userId: id, role })}
              users={users}
            />
          )}
        </div>
      </section>
      <SettingsModal email={user?.email} name={user?.name} onOpenChange={setSettingsOpen} open={settingsOpen} />
    </main>
  )
}

function AdminNavButton({ active, icon, label, onClick }: { active: boolean; icon: React.ReactElement; label: string; onClick: () => void }) {
  return (
    <button
      className={cn(
        'flex items-center gap-3 rounded-md border border-transparent px-3 py-3 text-left text-sm font-semibold text-fg-3 transition hover:bg-surface',
        active && 'border-border-brand bg-brand-soft text-fg-1',
      )}
      onClick={onClick}
      type="button"
    >
      {icon}
      {label}
    </button>
  )
}

function InsightsPanel() {
  return (
    <div>
      <h1 className="font-display text-3xl font-black text-fg-1">Insights</h1>
      <div className="mt-6 grid gap-4 md:grid-cols-3">
        <MetricCard label="Queries" value={String(ANALYTICS_SUMMARY.query_volume)} />
        <MetricCard label="Unanswered" value={String(ANALYTICS_SUMMARY.unanswered_count)} />
        <MetricCard label="Grounded rate" value={`${Math.round(ANALYTICS_SUMMARY.grounded_rate * 100)}%`} />
      </div>
      <Surface className="mt-5 p-5">
        <Badge tone="info">Fixture-backed until Phase 4 APIs land</Badge>
        <p className="mt-4 text-sm leading-6 text-fg-2">{DASHBOARD_INSIGHT.summary}</p>
        <Button className="mt-5" variant="secondary">
          <MessageCircle className="h-4 w-4" />
          Open analytics chat
        </Button>
      </Surface>
    </div>
  )
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <Surface className="p-5">
      <p className="text-sm text-fg-3">{label}</p>
      <p className="mt-2 font-display text-3xl font-black text-fg-1">{value}</p>
    </Surface>
  )
}

function KBPanel({ canManage, documents, onDelete, onRetry, onToggleOfficial }: {
  canManage: boolean
  documents: Array<{ id: string; title: string; processing_status: string; is_official: boolean; failure_reason: string | null }>
  onDelete: (id: string) => void
  onRetry: (id: string) => void
  onToggleOfficial: (id: string, isOfficial: boolean) => void
}) {
  return (
    <div>
      <h1 className="font-display text-3xl font-black text-fg-1">Knowledge base</h1>
      <div className="mt-6 grid gap-3">
        {documents.length === 0 && <Surface className="p-5 text-sm text-fg-3">No documents yet.</Surface>}
        {documents.map((doc) => (
          <Surface className="flex items-center justify-between gap-4 p-4" key={doc.id}>
            <div>
              <p className="text-sm font-semibold text-fg-1">{doc.title}</p>
              <p className="mt-1 text-xs text-fg-4">{doc.failure_reason ?? 'Visible to all athletes'}</p>
            </div>
            <div className="flex items-center gap-2">
              <Badge tone={doc.processing_status === 'failed' ? 'danger' : 'success'}>{doc.processing_status}</Badge>
              {canManage && (
                <>
                  <IconButton aria-label={`Retry ${doc.title}`} onClick={() => onRetry(doc.id)}>
                    <RefreshCw className="h-4 w-4" />
                  </IconButton>
                  <IconButton aria-label={`Toggle official ${doc.title}`} onClick={() => onToggleOfficial(doc.id, !doc.is_official)}>
                    <Shield className="h-4 w-4" />
                  </IconButton>
                  <IconButton aria-label={`Delete ${doc.title}`} onClick={() => onDelete(doc.id)}>
                    <Trash2 className="h-4 w-4" />
                  </IconButton>
                </>
              )}
            </div>
          </Surface>
        ))}
      </div>
    </div>
  )
}

function UsersPanel({ auditCount, onRoleChange, users }: {
  auditCount: number
  onRoleChange: (id: string, role: 'athlete' | 'admin' | 'super_admin') => void
  users: Array<{ id: string; name: string; email: string; role: 'athlete' | 'admin' | 'super_admin' }>
}) {
  return (
    <div>
      <h1 className="font-display text-3xl font-black text-fg-1">Users & roles</h1>
      <p className="mt-2 text-sm text-fg-3">{auditCount} audit events available.</p>
      <div className="mt-6 grid gap-3">
        {users.length === 0 && <Surface className="p-5 text-sm text-fg-3">No users returned yet.</Surface>}
        {users.map((adminUser) => (
          <Surface className="flex items-center justify-between gap-4 p-4" key={adminUser.id}>
            <div>
              <p className="text-sm font-semibold text-fg-1">{adminUser.name}</p>
              <p className="text-xs text-fg-4">{adminUser.email}</p>
            </div>
            <select
              className="rounded-md border border-border-strong bg-surface px-3 py-2 text-sm text-fg-1"
              onChange={(event) => onRoleChange(adminUser.id, event.target.value as 'athlete' | 'admin' | 'super_admin')}
              value={adminUser.role}
            >
              <option value="athlete">Athlete</option>
              <option value="admin">Admin</option>
              <option value="super_admin">Super admin</option>
            </select>
          </Surface>
        ))}
      </div>
    </div>
  )
}
