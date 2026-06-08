'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { ChatComposer, type ChatComposerHandle } from '@/src/components/features/chat/ChatComposer'
import { ChatNavRail } from '@/src/components/features/chat/ChatNavRail'
import { ChatSourcesPanel } from '@/src/components/features/chat/ChatSourcesPanel'
import { ChatThread } from '@/src/components/features/chat/ChatThread'
import { ChatTopBar } from '@/src/components/features/chat/ChatTopBar'
import { SettingsModal } from '@/src/components/features/common/SettingsModal'
import { HorizonBackground } from '@/src/components/features/common/HorizonBackground'
import { ChatWorkspaceSkeleton } from '@/src/components/features/loading/PlaybookLoaders'
import { WorkspaceShell } from '@/src/components/features/workspace/WorkspaceShell'
import { useCurrentUser, useLogout } from '@/src/hooks/useAuth'
import { useConversationDetail, useConversations, useCreateConversation } from '@/src/hooks/useConversations'
import { ROUTES } from '@/src/lib/constants/config'
import { useUIStore } from '@/src/lib/store/uiStore'
import type { ChatMessage, ConversationSummary, Citation } from '@/src/types/conversations'
import type { ConversationGroup } from './chatTypes'

const EMPTY_MESSAGES: ChatMessage[] = []
const EMPTY_CONVERSATIONS: ConversationSummary[] = []

export function ChatShell() {
  const router = useRouter()
  const composerRef = useRef<ChatComposerHandle | null>(null)
  const [pendingMessage, setPendingMessage] = useState<string | null>(null)
  const { data: user, isLoading: userLoading } = useCurrentUser()
  const conversationsQuery = useConversations()
  const conversations = conversationsQuery.data ?? EMPTY_CONVERSATIONS
  const activeConversationId = useUIStore((state) => state.activeConversationId)
  const selectedCitationTitle = useUIStore((state) => state.selectedCitationTitle)
  const setActiveConversationId = useUIStore((state) => state.setActiveConversationId)
  const setSelectedCitationTitle = useUIStore((state) => state.setSelectedCitationTitle)
  const sourcesOpen = useUIStore((state) => state.sourcesOpen)
  const setSourcesOpen = useUIStore((state) => state.setSourcesOpen)
  const toggleSources = useUIStore((state) => state.toggleSources)
  const settingsOpen = useUIStore((state) => state.settingsOpen)
  const setSettingsOpen = useUIStore((state) => state.setSettingsOpen)
  const conversationDetailQuery = useConversationDetail(activeConversationId)
  const activeConversation = conversationDetailQuery.data
  const createConversation = useCreateConversation()
  const logout = useLogout()

  useEffect(() => {
    if (!user || userLoading) return
    if (!user.profile_complete) {
      router.replace(ROUTES.profile)
      return
    }
    if (user.role !== 'athlete') {
      router.replace(ROUTES.admin)
    }
  }, [router, user, userLoading])

  const focusComposer = useCallback(() => {
    window.setTimeout(() => composerRef.current?.focus(), 0)
  }, [])

  const handleNewChat = useCallback(() => {
    setActiveConversationId(null)
    setSelectedCitationTitle(null)
    setSourcesOpen(false)
    focusComposer()
  }, [focusComposer, setActiveConversationId, setSelectedCitationTitle, setSourcesOpen])

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'n') {
        event.preventDefault()
        handleNewChat()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleNewChat])

  const conversationGroups = useMemo(() => groupConversations(conversations), [conversations])
  const messages = activeConversation?.messages ?? EMPTY_MESSAGES
  const conversationDetailLoading = Boolean(activeConversationId) && conversationDetailQuery.isLoading && !activeConversation
  const hasMessages = messages.length > 0
  const citations = useMemo(() => collectCitations(messages.flatMap((message) => message.citations)), [messages])
  const showSourcesPanel = hasMessages && sourcesOpen
  const activeConversationTitle = activeConversation?.title?.trim() || 'New chat'

  const handleSelectConversation = (conversationId: string) => {
    setPendingMessage(null)
    setActiveConversationId(conversationId)
    setSelectedCitationTitle(null)
    setSourcesOpen(true)
  }

  const handleSend = (message: string) => {
    setPendingMessage(message)
    createConversation.mutate(
      { initial_message: message },
      {
        onSuccess: (conversation) => {
          setPendingMessage(null)
          setActiveConversationId(conversation.id)
          setSelectedCitationTitle(null)
          setSourcesOpen(conversation.messages.some((chatMessage) => chatMessage.citations.length > 0))
        },
        onError: () => setPendingMessage(null),
      },
    )
  }

  const handleCitationSelect = (citation: Citation) => {
    setSelectedCitationTitle(citation.source_title)
  }

  const handleLogout = async () => {
    await logout.mutateAsync()
    router.push(ROUTES.login)
  }

  if (userLoading) return <ChatWorkspaceSkeleton />

  const leftRail = (
    <ChatNavRail
      activeConversationId={activeConversationId}
      groups={conversationGroups}
      isFetching={conversationsQuery.isFetching && !conversationsQuery.isLoading}
      isLoading={conversationsQuery.isLoading && conversations.length === 0}
      isLoggingOut={logout.isPending}
      onLogout={handleLogout}
      onNewChat={handleNewChat}
      onOpenSettings={() => setSettingsOpen(true)}
      onSelectConversation={handleSelectConversation}
      user={user}
    />
  )

  const main = (
    <section className="relative flex min-w-0 flex-1 flex-col overflow-hidden bg-bg-base">
      <div className="pointer-events-none absolute inset-0" aria-hidden="true">
        <HorizonBackground />
      </div>
      <div className="relative z-10 flex min-h-0 flex-1 flex-col">
        {hasMessages && (
          <ChatTopBar
            onToggleSources={toggleSources}
            sourcesOpen={sourcesOpen}
            title={activeConversationTitle}
          />
        )}
        <ChatThread
          isLoading={conversationDetailLoading}
          messages={messages}
          onCitationSelect={handleCitationSelect}
          pendingMessage={pendingMessage}
        />
        <ChatComposer disabled={createConversation.isPending} onSend={handleSend} ref={composerRef} />
      </div>
    </section>
  )

  const sidePanel = showSourcesPanel ? (
    <ChatSourcesPanel
      citations={citations}
      onClose={() => setSourcesOpen(false)}
      onSelectCitation={handleCitationSelect}
      selectedCitationTitle={selectedCitationTitle}
    />
  ) : undefined

  return (
    <>
      <WorkspaceShell leftRail={leftRail} main={main} sidePanel={sidePanel} />
      <SettingsModal
        onOpenChange={setSettingsOpen}
        open={settingsOpen}
        user={user}
      />
    </>
  )
}

function groupConversations(conversations: ConversationSummary[]): ConversationGroup[] {
  const grouped: Record<ConversationGroup['label'], ConversationSummary[]> = {
    Today: [],
    Yesterday: [],
    'Previous 7 days': [],
  }

  conversations
    .slice()
    .sort((left, right) => getConversationTimestamp(right) - getConversationTimestamp(left))
    .forEach((conversation) => {
      grouped[getConversationGroupLabel(conversation)].push(conversation)
    })

  return (['Today', 'Yesterday', 'Previous 7 days'] as const)
    .map((label) => ({ label, conversations: grouped[label] }))
    .filter((group) => group.conversations.length > 0)
}

function getConversationGroupLabel(conversation: ConversationSummary): ConversationGroup['label'] {
  const now = startOfDay(new Date())
  const timestamp = new Date(getConversationTimestamp(conversation))
  const conversationDay = startOfDay(timestamp)
  const daysAgo = Math.floor((now.getTime() - conversationDay.getTime()) / 86_400_000)

  if (daysAgo <= 0) return 'Today'
  if (daysAgo === 1) return 'Yesterday'
  return 'Previous 7 days'
}

function getConversationTimestamp(conversation: ConversationSummary) {
  return new Date(conversation.last_message_at ?? conversation.created_at).getTime()
}

function startOfDay(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate())
}

function collectCitations(citations: Citation[]) {
  const seen = new Set<string>()
  return citations.filter((citation) => {
    const key = citation.id || citation.source_title
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}
