'use client'

import { FormEvent, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { MessageCircle, PanelRightClose, PanelRightOpen, Plus, Search, Settings } from 'lucide-react'
import { SettingsModal } from '@/src/components/features/common/SettingsModal'
import { AgentAvatar, Badge, BrandLockup, Button, IconButton, Surface, Textarea } from '@/src/components/ui'
import { useCurrentUser, useLogout } from '@/src/hooks/useAuth'
import { useConversationDetail, useConversations, useCreateConversation } from '@/src/hooks/useConversations'
import { ROUTES } from '@/src/lib/constants/config'
import { useUIStore } from '@/src/lib/store/uiStore'
import { cn } from '@/src/lib/utils/cn'

export function ChatShell() {
  const router = useRouter()
  const { data: user, isLoading: userLoading } = useCurrentUser()
  const { data: conversations = [], isLoading: conversationsLoading } = useConversations()
  const activeConversationId = useUIStore((state) => state.activeConversationId)
  const setActiveConversationId = useUIStore((state) => state.setActiveConversationId)
  const sourcesOpen = useUIStore((state) => state.sourcesOpen)
  const toggleSources = useUIStore((state) => state.toggleSources)
  const settingsOpen = useUIStore((state) => state.settingsOpen)
  const setSettingsOpen = useUIStore((state) => state.setSettingsOpen)
  const { data: activeConversation } = useConversationDetail(activeConversationId)
  const createConversation = useCreateConversation()
  const logout = useLogout()
  const [draft, setDraft] = useState('')

  useEffect(() => {
    if (!user || userLoading) return
    if (user.role !== 'athlete') router.replace(ROUTES.admin)
    if (!user.profile_complete) router.replace(ROUTES.profile)
  }, [router, user, userLoading])

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const content = draft.trim()
    if (!content) return
    createConversation.mutate({ initial_message: content })
    setDraft('')
  }

  const handleLogout = async () => {
    await logout.mutateAsync()
    router.push(ROUTES.login)
  }

  const messages = activeConversation?.messages ?? []

  return (
    <main className="grid min-h-dvh grid-cols-[300px_minmax(0,1fr)] bg-bg-base text-fg-1 lg:grid-cols-[300px_minmax(0,1fr)_auto]">
      <aside className="flex min-h-dvh flex-col border-r border-border bg-bg-page p-4">
        <BrandLockup markSize={28} />
        <Button className="mt-6 w-full" onClick={() => setActiveConversationId(null)}>
          <Plus className="h-4 w-4" />
          New chat
        </Button>
        <div className="mt-5 flex items-center gap-2 rounded-md border border-border-strong bg-surface px-3 py-2 text-sm text-fg-4">
          <Search className="h-4 w-4" />
          Search conversations
        </div>
        <nav className="mt-5 flex flex-1 flex-col gap-2 overflow-auto" aria-label="Conversation history">
          {conversationsLoading && <p className="text-sm text-fg-3">Loading conversations...</p>}
          {conversations.map((conversation) => (
            <button
              className={cn(
                'rounded-md border border-transparent p-3 text-left text-sm text-fg-2 transition hover:border-border-strong hover:bg-surface',
                activeConversationId === conversation.id && 'border-border-brand bg-brand-soft text-fg-1',
              )}
              key={conversation.id}
              onClick={() => setActiveConversationId(conversation.id)}
              type="button"
            >
              <span className="block font-semibold">{conversation.title ?? 'Untitled conversation'}</span>
              <span className="text-xs text-fg-4">{conversation.status}</span>
            </button>
          ))}
        </nav>
        <div className="mt-4 rounded-md border border-border-strong bg-surface p-3">
          <p className="text-sm font-semibold text-fg-1">{user?.name ?? 'Athlete'}</p>
          <p className="text-xs text-fg-4">{user?.email ?? 'Signed in with SSO'}</p>
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

      <section className="relative flex min-h-dvh flex-col overflow-hidden">
        <div className="pb-ambient-grid pointer-events-none absolute inset-0 opacity-60" />
        <header className="relative z-10 flex items-center justify-between border-b border-border px-6 py-4">
          <div>
            <p className="text-sm font-semibold text-fg-1">{activeConversation?.title ?? 'Ask PlaybookAI'}</p>
            <p className="text-xs text-fg-4">Entire knowledge base</p>
          </div>
          <IconButton aria-label="Toggle sources" onClick={toggleSources}>
            {sourcesOpen ? <PanelRightClose className="h-4 w-4" /> : <PanelRightOpen className="h-4 w-4" />}
          </IconButton>
        </header>
        <div className="relative z-10 flex flex-1 flex-col justify-end overflow-auto px-6 py-8">
          {messages.length === 0 ? (
            <div className="mx-auto mb-12 max-w-2xl text-center">
              <AgentAvatar className="mx-auto h-12 w-12" />
              <h1 className="mt-5 font-display text-4xl font-black text-fg-1">Ask PlaybookAI</h1>
              <p className="mt-3 text-sm text-fg-3">Get grounded answers from your department knowledge base.</p>
            </div>
          ) : (
            <div className="mx-auto flex w-full max-w-[760px] flex-col gap-6">
              {messages.map((message) => (
                <Surface className="p-4" key={message.id}>
                  <div className="flex gap-3">
                    {message.role !== 'user' && <AgentAvatar />}
                    <div>
                      <Badge tone={message.role === 'user' ? 'neutral' : 'brand'}>{message.role}</Badge>
                      <p className="mt-3 text-sm leading-6 text-fg-2">{message.content}</p>
                    </div>
                  </div>
                </Surface>
              ))}
            </div>
          )}
        </div>
        <form className="relative z-10 border-t border-border bg-bg-base/90 px-6 py-4" onSubmit={handleSubmit}>
          <div className="mx-auto flex max-w-[760px] gap-3">
            <Textarea
              aria-label="Message Playbook"
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault()
                  event.currentTarget.form?.requestSubmit()
                }
              }}
              placeholder="Ask about NIL, compliance, travel, academics, or internal process..."
              rows={2}
              value={draft}
            />
            <Button disabled={createConversation.isPending} type="submit">
              <MessageCircle className="h-4 w-4" />
              Send
            </Button>
          </div>
        </form>
      </section>

      {sourcesOpen && (
        <aside className="hidden w-[340px] border-l border-border bg-bg-page p-5 lg:block">
          <h2 className="text-sm font-bold text-fg-1">Grounding sources</h2>
          <div className="mt-4 grid gap-3">
            {['NIL policy handbook', 'Team travel guide', 'Academic services overview'].map((source) => (
              <Surface className="p-3" interactive key={source}>
                <p className="text-sm font-semibold text-fg-1">{source}</p>
                <p className="mt-1 text-xs text-fg-4">Available after retrieval-backed answers land.</p>
              </Surface>
            ))}
          </div>
        </aside>
      )}

      <SettingsModal
        email={user?.email}
        name={user?.name}
        onOpenChange={setSettingsOpen}
        open={settingsOpen}
      />
    </main>
  )
}
