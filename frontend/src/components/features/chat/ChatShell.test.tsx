import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ChatShell } from '@/src/components/features/chat/ChatShell'
import { useUIStore } from '@/src/lib/store/uiStore'
import type { ConversationDetail, ConversationSummary } from '@/src/types/conversations'

const chatMocks = vi.hoisted(() => ({
  conversations: [] as ConversationSummary[],
  createConversationMutate: vi.fn(),
  details: new Map<string, ConversationDetail>(),
  logoutMutateAsync: vi.fn(),
  routerPush: vi.fn(),
  routerReplace: vi.fn(),
}))

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: chatMocks.routerPush, replace: chatMocks.routerReplace }),
}))

vi.mock('@/src/hooks/useAuth', () => ({
  useCurrentUser: () => ({
    data: {
      id: 'user-1',
      organization_id: 'org-1',
      name: 'Jordan Mitchell',
      email: 'j.mitchell@okstate.edu',
      role: 'athlete',
      sport_team: 'OSU Athletics',
      profile_complete: true,
      is_active: true,
    },
    isLoading: false,
  }),
  useLogout: () => ({ mutateAsync: chatMocks.logoutMutateAsync, isPending: false }),
}))

vi.mock('@/src/hooks/useConversations', () => ({
  useConversations: () => ({ data: chatMocks.conversations, isLoading: false }),
  useCreateConversation: () => ({ mutate: chatMocks.createConversationMutate, isPending: false }),
  useConversationDetail: (conversationId: string | null) => ({
    data: conversationId ? chatMocks.details.get(conversationId) : undefined,
    isLoading: false,
  }),
}))

const today = new Date('2026-06-08T15:30:00.000Z')
const yesterday = new Date('2026-06-07T15:30:00.000Z')
const previous = new Date('2026-06-03T15:30:00.000Z')

function summary(id: string, title: string | null, createdAt: Date): ConversationSummary {
  return {
    id,
    organization_id: 'org-1',
    athlete_id: 'user-1',
    title,
    status: 'active',
    last_message_at: createdAt.toISOString(),
    created_at: createdAt.toISOString(),
    updated_at: createdAt.toISOString(),
  }
}

function detail(summaryRecord: ConversationSummary): ConversationDetail {
  return { ...summaryRecord, messages: [] }
}

function renderChat() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <ChatShell />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  chatMocks.conversations = []
  chatMocks.details = new Map()
  chatMocks.routerPush.mockReset()
  chatMocks.routerReplace.mockReset()
  chatMocks.logoutMutateAsync.mockReset()
  chatMocks.createConversationMutate.mockReset()
  useUIStore.setState({
    activeConversationId: null,
    sourcesOpen: true,
    selectedCitationTitle: null,
    settingsOpen: false,
    adminTab: 'insights',
  })
})

describe('ChatShell', () => {
  it('renders the design empty state without a top bar or sources panel', () => {
    renderChat()

    expect(screen.getByRole('heading', { name: /ask playbookai/i })).toBeInTheDocument()
    expect(screen.getByText(/get answers to your athletics questions,/i)).toBeInTheDocument()
    expect(screen.getByText(/playbookai is your coach off the field\./i)).toBeInTheDocument()
    expect(screen.getByText(/responses are ai generated\. review to confirm accuracy\./i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /attach file/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^ask$/i })).toBeDisabled()
    expect(screen.queryByRole('banner', { name: /chat actions/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('complementary', { name: /sources/i })).not.toBeInTheDocument()
  })

  it('groups conversation history and filters search results', async () => {
    const todayConversation = summary('c1', 'NIL disclosure window', today)
    const yesterdayConversation = summary('c2', 'Student section entry rules', yesterday)
    const previousConversation = summary('c3', 'Reserving the indoor field', previous)
    chatMocks.conversations = [todayConversation, yesterdayConversation, previousConversation]
    chatMocks.details = new Map([
      ['c1', detail(todayConversation)],
      ['c2', detail(yesterdayConversation)],
      ['c3', detail(previousConversation)],
    ])

    renderChat()

    expect(screen.getByText('Today')).toBeInTheDocument()
    expect(screen.getByText('Yesterday')).toBeInTheDocument()
    expect(screen.getByText('Previous 7 days')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /nil disclosure window/i })).toBeInTheDocument()

    await userEvent.type(screen.getByPlaceholderText(/search chats/i), 'student')

    expect(screen.queryByRole('button', { name: /nil disclosure window/i })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /student section entry rules/i })).toBeInTheDocument()
  })

  it('clears the active conversation and focuses the composer when starting a new chat', async () => {
    const todayConversation = summary('c1', 'NIL disclosure window', today)
    chatMocks.conversations = [todayConversation]
    chatMocks.details = new Map([['c1', detail(todayConversation)]])
    useUIStore.setState({ activeConversationId: 'c1' })

    renderChat()

    await userEvent.click(screen.getByRole('button', { name: /new chat/i }))

    expect(screen.getByRole('heading', { name: /ask playbookai/i })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByLabelText(/message playbook/i)).toHaveFocus())
  })

  it('uses one composite focus shell for chat text fields', () => {
    renderChat()

    const composer = screen.getByLabelText(/message playbook/i)
    const composerShell = composer.closest('.pb-field-shell')
    const search = screen.getByPlaceholderText(/search chats/i)
    const searchShell = search.closest('.pb-field-shell')

    expect(composerShell).toBeInTheDocument()
    expect(searchShell).toBeInTheDocument()
    expect(composer).not.toHaveClass('shadow-focus')
    expect(search).not.toHaveClass('shadow-focus')
  })

  it('submits non-empty composer text while preserving multiline drafts', async () => {
    renderChat()
    const textarea = screen.getByLabelText(/message playbook/i)

    await userEvent.type(textarea, 'Can I travel?')
    await userEvent.click(screen.getByRole('button', { name: /^ask$/i }))

    expect(chatMocks.createConversationMutate).toHaveBeenCalledWith(
      { initial_message: 'Can I travel?' },
      expect.objectContaining({ onSuccess: expect.any(Function) }),
    )

    await userEvent.type(textarea, 'Line one{shift>}{enter}{/shift}Line two')
    expect(textarea).toHaveValue('Line one\nLine two')
  })

  it('opens sources from a citation click and highlights the cited source', async () => {
    const conversation = summary('c1', 'NIL disclosure window', today)
    chatMocks.conversations = [conversation]
    chatMocks.details = new Map([
      [
        'c1',
        {
          ...conversation,
          messages: [
            {
              id: 'm1',
              conversation_id: 'c1',
              role: 'assistant',
              content: 'Athletes disclose NIL agreements within 72 hours.',
              status: 'complete',
              safety_outcome: null,
              topic_labels: [],
              risk_labels: [],
              metadata: { checked_sources: 4, response_time: '1.8s' },
              citations: [
                {
                  id: 'citation-1',
                  message_id: 'm1',
                  document_id: 'doc-1',
                  chunk_id: 'chunk-1',
                  source_title: 'NIL policy handbook',
                  source_metadata: { page: 'p. 4' },
                  rank: 1,
                  created_at: today.toISOString(),
                },
              ],
              created_at: today.toISOString(),
            },
          ],
        },
      ],
    ])
    useUIStore.setState({ activeConversationId: 'c1', sourcesOpen: false })

    renderChat()

    await userEvent.click(screen.getByRole('button', { name: /nil policy handbook/i }))

    const panel = screen.getByRole('complementary', { name: /sources/i })
    expect(panel).toBeInTheDocument()
    expect(within(panel).getAllByText('NIL policy handbook')).toHaveLength(2)
    expect(within(panel).getByText(/selected source/i)).toBeInTheDocument()
  })

  it('opens the account menu, settings modal, and logout action', async () => {
    renderChat()

    await userEvent.click(screen.getByRole('button', { name: /jordan mitchell account menu/i }))
    await userEvent.click(screen.getByRole('menuitem', { name: /settings/i }))

    expect(screen.getByRole('dialog', { name: /settings/i })).toBeInTheDocument()

    await userEvent.keyboard('{Escape}')
    await userEvent.click(screen.getByRole('button', { name: /jordan mitchell account menu/i }))
    await userEvent.click(screen.getByRole('menuitem', { name: /sign out/i }))

    expect(chatMocks.logoutMutateAsync).toHaveBeenCalledOnce()
  })
})
