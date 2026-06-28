'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useQueryClient } from '@tanstack/react-query'
import { ChatComposer, type ChatComposerHandle } from '@/src/components/features/chat/ChatComposer'
import { ChatNavRail } from '@/src/components/features/chat/ChatNavRail'
import { ChatSourcesPanel } from '@/src/components/features/chat/ChatSourcesPanel'
import { ChatThread } from '@/src/components/features/chat/ChatThread'
import { ChatTopBar } from '@/src/components/features/chat/ChatTopBar'
import { collectUniqueCitations, groupConversations } from '@/src/components/features/chat/conversationGrouping'
import {
  useChatFileUploads,
  type UploadConversationFileMutation,
} from '@/src/components/features/chat/useChatFileUploads'
import { SettingsModal } from '@/src/components/features/common/SettingsModal'
import { HorizonBackground } from '@/src/components/features/common/HorizonBackground'
import { ChatWorkspaceSkeleton } from '@/src/components/features/loading/PlaybookLoaders'
import { WorkspaceShell } from '@/src/components/features/workspace/WorkspaceShell'
import { useCurrentUser, useLogout } from '@/src/hooks/useAuth'
import {
  createSubmittedMessages,
  useConversationDetail,
  useConversationMessageStream,
  useConversations,
  useCreateConversation,
  useSubmitConversationMessage,
  useUploadConversationFile,
} from '@/src/hooks/useConversations'
import { useSessionActivity } from '@/src/hooks/useSessionActivity'
import { QUERY_KEYS, ROUTES } from '@/src/lib/constants/config'
import { useUIStore } from '@/src/lib/store/uiStore'
import type {
  ChatMessage,
  ConversationDetail,
  ConversationSummary,
  Citation,
  MessageSubmitResponse,
} from '@/src/types/conversations'

const EMPTY_MESSAGES: ChatMessage[] = []
const EMPTY_CONVERSATIONS: ConversationSummary[] = []

export function ChatShell() {
  const router = useRouter()
  const queryClient = useQueryClient()
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
  const submitConversationMessage = useSubmitConversationMessage()
  const { start: startConversationStream, stop: stopConversationStream } = useConversationMessageStream()
  const uploadConversationFile = useUploadConversationFile()
  const uploadConversationFileMutation = useCallback<UploadConversationFileMutation>(
    (request, options) => uploadConversationFile.mutate(request, options),
    [uploadConversationFile],
  )
  const {
    clearLocalUploads,
    handleAttachFile,
    localUploads,
    uploadPendingFiles,
  } = useChatFileUploads({
    activeConversationId,
    uploadConversationFile: uploadConversationFileMutation,
  })
  const logout = useLogout()
  useSessionActivity({ enabled: Boolean(user) && !userLoading })

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
    stopConversationStream()
    setActiveConversationId(null)
    clearLocalUploads()
    setSelectedCitationTitle(null)
    setSourcesOpen(false)
    focusComposer()
  }, [clearLocalUploads, focusComposer, setActiveConversationId, setSelectedCitationTitle, setSourcesOpen, stopConversationStream])

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
  const citations = useMemo(() => collectUniqueCitations(messages.flatMap((message) => message.citations)), [messages])
  const showSourcesPanel = hasMessages && sourcesOpen
  const activeConversationTitle = activeConversation?.title?.trim() || 'New chat'
  const conversationFiles = activeConversation?.files ?? []

  const handleSelectConversation = (conversationId: string) => {
    setPendingMessage(null)
    stopConversationStream()
    clearLocalUploads()
    setActiveConversationId(conversationId)
    setSelectedCitationTitle(null)
  }

  const appendSubmittedTurn = useCallback(
    (conversationId: string, message: string, response: MessageSubmitResponse) => {
      queryClient.setQueryData<ConversationDetail>(
        [QUERY_KEYS.conversationDetail, conversationId],
        (conversation) => {
          if (!conversation) return conversation
          return {
            ...conversation,
            messages: [
              ...conversation.messages,
              ...createSubmittedMessages(conversationId, message, response),
            ],
          }
        },
      )
    },
    [queryClient],
  )

  const handleSend = (message: string) => {
    setPendingMessage(message)
    if (activeConversationId) {
      submitConversationMessage.mutate(
        { conversationId: activeConversationId, content: message },
        {
          onSuccess: (response) => {
            setPendingMessage(null)
            appendSubmittedTurn(activeConversationId, message, response)
            setSelectedCitationTitle(null)
            setSourcesOpen(false)
            startConversationStream({
              assistantMessageId: response.assistant_message_id,
              conversationId: activeConversationId,
              streamUrl: response.stream_url,
            })
          },
          onError: () => setPendingMessage(null),
        },
      )
      return
    }

    createConversation.mutate(
      { content: message },
      {
        onSuccess: (response) => {
          const conversation = response.conversation
          setPendingMessage(null)
          setActiveConversationId(conversation.id)
          setSelectedCitationTitle(null)
          setSourcesOpen(false)
          uploadPendingFiles(conversation.id)
          startConversationStream({
            assistantMessageId: response.assistant_message_id,
            conversationId: conversation.id,
            streamUrl: response.stream_url,
          })
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
          conversationId={activeConversationId}
          isLoading={conversationDetailLoading}
          messages={messages}
          onCitationSelect={handleCitationSelect}
          pendingMessage={pendingMessage}
        />
        <ChatComposer
          canAttach
          conversationFiles={conversationFiles}
          disabled={createConversation.isPending || submitConversationMessage.isPending}
          localUploads={localUploads}
          onAttachFile={handleAttachFile}
          onSend={handleSend}
          ref={composerRef}
        />
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
