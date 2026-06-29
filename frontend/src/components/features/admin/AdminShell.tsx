'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Lock } from 'lucide-react'
import { AdminChatPanel } from '@/src/components/features/admin/AdminChatPanel'
import { AdminInsightsDashboard } from '@/src/components/features/admin/AdminInsightsDashboard'
import { AdminNav } from '@/src/components/features/admin/AdminNav'
import { KBPanel } from '@/src/components/features/admin/AdminPanels'
import { AdminUsersPanel } from '@/src/components/features/admin/AdminUsersPanel'
import { SettingsModal } from '@/src/components/features/common/SettingsModal'
import { AdminWorkspaceSkeleton } from '@/src/components/features/loading/PlaybookLoaders'
import { WorkspaceShell } from '@/src/components/features/workspace/WorkspaceShell'
import { Button } from '@/src/components/ui'
import { useAdminUsers, useUpdateUserRole } from '@/src/hooks/useAdmin'
import { useCurrentUser, useLogout } from '@/src/hooks/useAuth'
import {
  useDeleteKBDocument,
  useKBDocuments,
  useRetryKBDocument,
  useUpdateKBDocumentMetadata,
  useUploadKBDocument,
} from '@/src/hooks/useKBDocuments'
import { useSessionActivity } from '@/src/hooks/useSessionActivity'
import { adminChatReply, ANALYTICS_SUMMARY, DASHBOARD_INSIGHT } from '@/src/lib/fixtures/admin'
import { ROUTES } from '@/src/lib/constants/config'
import { useUIStore } from '@/src/lib/store/uiStore'

export function AdminShell() {
  const router = useRouter()
  const { data: user, isLoading } = useCurrentUser()
  const logout = useLogout()
  const adminTab = useUIStore((state) => state.adminTab)
  const setAdminTab = useUIStore((state) => state.setAdminTab)
  const settingsOpen = useUIStore((state) => state.settingsOpen)
  const setSettingsOpen = useUIStore((state) => state.setSettingsOpen)
  const adminChatOpen = useUIStore((state) => state.adminChatOpen)
  const setAdminChatOpen = useUIStore((state) => state.setAdminChatOpen)
  const adminTimeWindow = useUIStore((state) => state.adminTimeWindow)
  const setAdminTimeWindow = useUIStore((state) => state.setAdminTimeWindow)
  const adminInsightStatus = useUIStore((state) => state.adminInsightStatus)
  const setAdminInsightStatus = useUIStore((state) => state.setAdminInsightStatus)
  const adminChatMessages = useUIStore((state) => state.adminChatMessages)
  const addAdminChatMessage = useUIStore((state) => state.addAdminChatMessage)
  const isSuperAdmin = user?.role === 'super_admin'
  const isAdmin = user?.role === 'admin' || isSuperAdmin
  const documentsQuery = useKBDocuments()
  const documents = documentsQuery.data ?? []
  const usersQuery = useAdminUsers(Boolean(isSuperAdmin))
  const users = usersQuery.data ?? []
  const retryDocument = useRetryKBDocument()
  const deleteDocument = useDeleteKBDocument()
  const updateDocument = useUpdateKBDocumentMetadata()
  const uploadDocument = useUploadKBDocument()
  const updateRole = useUpdateUserRole()
  const failedDocsCount = documents.filter((document) => document.processing_status === 'failed').length
  useSessionActivity({ enabled: Boolean(user) && !isLoading })

  useEffect(() => {
    if (!isSuperAdmin && adminTab === 'users') setAdminTab('insights')
  }, [adminTab, isSuperAdmin, setAdminTab])

  if (isLoading) return <AdminWorkspaceSkeleton />

  if (!isAdmin) {
    return (
      <main className="pb-stage flex min-h-dvh items-center justify-center p-6 text-center">
        <div className="max-w-md">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-lg border border-border-strong bg-surface">
            <Lock className="h-7 w-7 text-fg-3" />
          </div>
          <h1 className="pb-h2 mt-5">Admins only</h1>
          <p className="pb-body mt-3">
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

  const handleGenerate = () => {
    setAdminInsightStatus('processing')
    window.setTimeout(() => setAdminInsightStatus('completed'), 2200)
  }

  const handleSendAdminChatMessage = (content: string) => {
    const idBase = Date.now()
    addAdminChatMessage({ id: `admin-user-${idBase}`, role: 'user', content })
    const reply = adminChatReply(content)
    addAdminChatMessage({
      id: `admin-assistant-${idBase}`,
      role: 'assistant',
      content: reply.answer,
      refs: reply.refs,
      answer_type: reply.answer_type,
    })
  }

  const leftRail = (
    <AdminNav
      activeTab={adminTab}
      failedDocsCount={failedDocsCount}
      isLoggingOut={logout.isPending}
      isSuperAdmin={Boolean(isSuperAdmin)}
      onLogout={handleLogout}
      onNavigate={setAdminTab}
      onOpenSettings={() => setSettingsOpen(true)}
      onOpenChatWorkspace={() => router.push(ROUTES.chat)}
      user={user}
    />
  )

  const main = (
    <section className="relative flex min-w-0 flex-1 flex-col overflow-hidden bg-bg-base">
      <div className="admin-grid opacity-70" aria-hidden="true" />
      <div className="relative z-10 min-h-0 flex-1 overflow-y-auto">
        {adminTab === 'insights' && (
          <AdminInsightsDashboard
            insight={DASHBOARD_INSIGHT}
            insightStatus={adminInsightStatus}
            onGenerate={handleGenerate}
            onOpenChat={() => setAdminChatOpen(true)}
            onTimeWindowChange={setAdminTimeWindow}
            summary={ANALYTICS_SUMMARY}
            timeWindow={adminTimeWindow}
          />
        )}
        {adminTab === 'kb' && (
          <KBPanel
            canManage={Boolean(isSuperAdmin)}
            documents={documents}
            isError={documentsQuery.isError}
            isFetching={documentsQuery.isFetching && !documentsQuery.isLoading}
            isLoading={documentsQuery.isLoading && documents.length === 0}
            onDelete={(id) => deleteDocument.mutate(id)}
            onRetry={(id) => retryDocument.mutate(id)}
            onUpdateMetadata={(documentId, metadata) => updateDocument.mutate({ documentId, metadata })}
            onUpload={(request) => uploadDocument.mutateAsync(request)}
          />
        )}
        {adminTab === 'users' && isSuperAdmin && (
          <AdminUsersPanel
            currentUserId={user?.id}
            isError={usersQuery.isError}
            isFetching={usersQuery.isFetching && !usersQuery.isLoading}
            isLoading={usersQuery.isLoading && users.length === 0}
            onRoleChange={(id, role) => updateRole.mutate({ userId: id, role })}
            users={users}
          />
        )}
      </div>
    </section>
  )

  const sidePanel = adminChatOpen ? (
    <AdminChatPanel
      messages={adminChatMessages}
      onClose={() => setAdminChatOpen(false)}
      onSend={handleSendAdminChatMessage}
    />
  ) : undefined

  return (
    <>
      <WorkspaceShell leftRail={leftRail} main={main} sidePanel={sidePanel} />
      <SettingsModal onOpenChange={setSettingsOpen} open={settingsOpen} user={user} />
    </>
  )
}
