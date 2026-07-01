'use client'

import { useCallback, useEffect, useState } from 'react'
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
import {
  useAdminChatMessageStream,
  useAdminChatSessionDetail,
  useAdminChatSessions,
  useCreateAdminChatSession,
  useSubmitAdminChatMessage,
} from '@/src/hooks/useAdminChat'
import { useAdminUsers, useUpdateUserRole } from '@/src/hooks/useAdmin'
import { useCurrentUser, useLogout } from '@/src/hooks/useAuth'
import {
  useDeleteKBDocument,
  useArchiveKBMetadataTag,
  useCreateKBCollection,
  useCreateKBMetadataTag,
  useDeleteKBCollection,
  useDeleteKBMetadataTagPermanently,
  useKBCollections,
  useKBMetadataTags,
  useKBDocuments,
  useRetryKBDocument,
  useUpdateKBMetadataTag,
  useUnarchiveKBMetadataTag,
  useUpdateKBDocumentMetadata,
  useUploadKBDocument,
} from '@/src/hooks/useKBDocuments'
import { useSessionActivity } from '@/src/hooks/useSessionActivity'
import { ANALYTICS_SUMMARY, DASHBOARD_INSIGHT } from '@/src/lib/fixtures/admin'
import { ROUTES } from '@/src/lib/constants/config'
import { useUIStore } from '@/src/lib/store/uiStore'
import type { AdminChatMessage } from '@/src/types/adminChat'

const EMPTY_ADMIN_CHAT_MESSAGES: AdminChatMessage[] = []

export function AdminShell() {
  const router = useRouter()
  const [adminChatSessionId, setAdminChatSessionId] = useState<string | null>(null)
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
  const isSuperAdmin = user?.role === 'super_admin'
  const isAdmin = user?.role === 'admin' || isSuperAdmin
  const documentsQuery = useKBDocuments()
  const documents = documentsQuery.data ?? []
  const collectionsQuery = useKBCollections()
  const collections = collectionsQuery.data ?? []
  const metadataTagsQuery = useKBMetadataTags()
  const metadataTags = metadataTagsQuery.data ?? []
  const usersQuery = useAdminUsers(Boolean(isSuperAdmin))
  const users = usersQuery.data ?? []
  const retryDocument = useRetryKBDocument()
  const deleteDocument = useDeleteKBDocument()
  const updateDocument = useUpdateKBDocumentMetadata()
  const uploadDocument = useUploadKBDocument()
  const createCollection = useCreateKBCollection()
  const deleteCollection = useDeleteKBCollection()
  const createMetadataTag = useCreateKBMetadataTag()
  const updateMetadataTag = useUpdateKBMetadataTag()
  const archiveMetadataTag = useArchiveKBMetadataTag()
  const unarchiveMetadataTag = useUnarchiveKBMetadataTag()
  const deleteMetadataTagPermanently = useDeleteKBMetadataTagPermanently()
  const updateRole = useUpdateUserRole()
  const adminChatSessionsQuery = useAdminChatSessions(Boolean(isAdmin) && adminChatOpen)
  const latestAdminChatSessionId = adminChatSessionsQuery.data?.[0]?.id ?? null
  const adminChatSessionQuery = useAdminChatSessionDetail(
    adminChatSessionId,
    Boolean(isAdmin) && adminChatOpen,
  )
  const createAdminChatSession = useCreateAdminChatSession()
  const submitAdminChatMessage = useSubmitAdminChatMessage()
  const { start: startAdminChatStream } = useAdminChatMessageStream()
  const adminChatMessages = adminChatSessionQuery.data?.messages ?? EMPTY_ADMIN_CHAT_MESSAGES
  const adminChatBusy =
    createAdminChatSession.isPending ||
    submitAdminChatMessage.isPending ||
    adminChatMessages.some((message) => message.status === 'streaming')
  const adminChatError =
    adminChatSessionsQuery.isError ||
    adminChatSessionQuery.isError ||
    createAdminChatSession.isError ||
    submitAdminChatMessage.isError
  const adminChatLoading = Boolean(adminChatSessionId) && adminChatSessionQuery.isLoading && adminChatMessages.length === 0
  const failedDocsCount = documents.filter((document) => document.processing_status === 'failed').length
  useSessionActivity({ enabled: Boolean(user) && !isLoading })

  useEffect(() => {
    if (!isSuperAdmin && adminTab === 'users') setAdminTab('insights')
  }, [adminTab, isSuperAdmin, setAdminTab])

  useEffect(() => {
    if (!adminChatOpen || adminChatSessionId || !latestAdminChatSessionId) return
    setAdminChatSessionId(latestAdminChatSessionId)
  }, [adminChatOpen, adminChatSessionId, latestAdminChatSessionId])

  const ensureAdminChatSession = useCallback(
    async (content: string): Promise<string> => {
      if (adminChatSessionId) return adminChatSessionId
      const session = await createAdminChatSession.mutateAsync({
        title: createAdminChatTitle(content),
      })
      setAdminChatSessionId(session.id)
      return session.id
    },
    [adminChatSessionId, createAdminChatSession],
  )

  const handleSendAdminChatMessage = useCallback(
    (content: string) => {
      void (async () => {
        try {
          const sessionId = await ensureAdminChatSession(content)
          const response = await submitAdminChatMessage.mutateAsync({
            sessionId,
            question: content,
            window: adminTimeWindow === 'custom' ? undefined : adminTimeWindow,
          })
          startAdminChatStream({
            assistantMessageId: response.assistant_message_id,
            sessionId,
            streamUrl: response.stream_url,
          })
        } catch {
          // Mutation state renders the recoverable panel error.
        }
      })()
    },
    [adminTimeWindow, ensureAdminChatSession, startAdminChatStream, submitAdminChatMessage],
  )

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
            canCreateCollection={Boolean(isSuperAdmin)}
            canDeleteCollection={Boolean(isSuperAdmin)}
            canManageDocuments={Boolean(isAdmin)}
            canManageTags={Boolean(isSuperAdmin)}
            collections={collections}
            documents={documents}
            isError={documentsQuery.isError || collectionsQuery.isError}
            isFetching={
              (documentsQuery.isFetching && !documentsQuery.isLoading) ||
              (collectionsQuery.isFetching && !collectionsQuery.isLoading)
            }
            isLoading={
              (documentsQuery.isLoading && documents.length === 0) ||
              (collectionsQuery.isLoading && collections.length === 0)
            }
            metadataTags={metadataTags}
            onArchiveMetadataTag={(tagId) => archiveMetadataTag.mutateAsync(tagId)}
            onCreateCollection={(request) => createCollection.mutateAsync(request)}
            onCreateMetadataTag={(request) => createMetadataTag.mutateAsync(request)}
            onDeleteCollection={(collectionId) => deleteCollection.mutateAsync(collectionId)}
            onDeleteMetadataTagPermanently={(tagId) => deleteMetadataTagPermanently.mutateAsync(tagId)}
            onDelete={(id) => deleteDocument.mutate(id)}
            onRetry={(id) => retryDocument.mutate(id)}
            onUnarchiveMetadataTag={(tagId) => unarchiveMetadataTag.mutateAsync(tagId)}
            onUpdateMetadata={(documentId, metadata) => updateDocument.mutateAsync({ documentId, metadata })}
            onUpdateMetadataTag={(tagId, request) => updateMetadataTag.mutateAsync({ tagId, request })}
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
      isBusy={adminChatBusy}
      isError={adminChatError}
      isLoading={adminChatLoading}
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

function createAdminChatTitle(content: string): string {
  const trimmed = content.trim()
  if (!trimmed) return 'Analytics chat'
  return trimmed.length > 80 ? `${trimmed.slice(0, 77)}...` : trimmed
}
