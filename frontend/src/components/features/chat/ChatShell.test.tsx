import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ChatShell } from '@/src/components/features/chat/ChatShell'
import { useUIStore } from '@/src/lib/store/uiStore'
import type { ConversationDetail, ConversationSummary } from '@/src/types/conversations'

const chatMocks = vi.hoisted(() => ({
  conversations: [] as ConversationSummary[],
  conversationsFetching: false,
  conversationsLoading: false,
  createConversationMutate: vi.fn(),
  createConversationPending: false,
  detailFetching: false,
  detailLoading: false,
  details: new Map<string, ConversationDetail>(),
  logoutMutateAsync: vi.fn(),
  routerPush: vi.fn(),
  routerReplace: vi.fn(),
}))

const currentUser = vi.hoisted(() => ({
  isLoading: false,
  role: 'athlete',
}))

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: chatMocks.routerPush, replace: chatMocks.routerReplace }),
}))

vi.mock('@/src/hooks/useAuth', () => ({
  useCurrentUser: () => ({
    data: currentUser.isLoading
      ? undefined
      : {
          id: 'user-1',
          organization_id: 'org-1',
          name: 'Jordan Mitchell',
          email: 'j.mitchell@okstate.edu',
          role: currentUser.role,
          sport_team: 'OSU Athletics',
          profile_complete: true,
          is_active: true,
        },
    isLoading: currentUser.isLoading,
  }),
  useLogout: () => ({ mutateAsync: chatMocks.logoutMutateAsync, isPending: false }),
}))

vi.mock('@/src/hooks/useConversations', () => ({
  useConversations: () => ({
    data: chatMocks.conversationsLoading ? undefined : chatMocks.conversations,
    isFetching: chatMocks.conversationsFetching,
    isLoading: chatMocks.conversationsLoading,
  }),
  useCreateConversation: () => ({
    mutate: chatMocks.createConversationMutate,
    isPending: chatMocks.createConversationPending,
  }),
  useConversationDetail: (conversationId: string | null) => ({
    data: conversationId && !chatMocks.detailLoading ? chatMocks.details.get(conversationId) : undefined,
    isFetching: chatMocks.detailFetching,
    isLoading: chatMocks.detailLoading,
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
  chatMocks.conversationsFetching = false
  chatMocks.conversationsLoading = false
  chatMocks.createConversationPending = false
  chatMocks.detailFetching = false
  chatMocks.detailLoading = false
  chatMocks.details = new Map()
  currentUser.isLoading = false
  currentUser.role = 'athlete'
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
  it('renders a workspace skeleton while auth resolves', () => {
    currentUser.isLoading = true

    renderChat()

    expect(screen.getByTestId('chat-workspace-skeleton')).toBeInTheDocument()
    expect(screen.getByTestId('chat-empty-skeleton')).toBeInTheDocument()
    expect(screen.getByTestId('chat-composer-shell')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /ask playbookai/i })).toBeInTheDocument()
    const newChat = screen.getByRole('button', { name: /new chat/i })
    const searchChats = screen.getByPlaceholderText(/search chats/i)
    const askButton = screen.getByRole('button', { name: /^ask$/i })

    expect(newChat).toHaveClass('pb-ui-sm')
    expect(newChat).toHaveClass('font-semibold')
    expect(searchChats).toBeDisabled()
    expect(askButton).toBeDisabled()
    expect(askButton).toHaveClass('disabled:bg-surface-raised')
    expect(screen.queryByText(/get answers to your athletics questions/i)).not.toBeInTheDocument()
    expect(screen.getByText(/responses are ai generated/i)).toBeInTheDocument()
    expect(screen.queryByTestId('chat-composer-content-skeleton')).not.toBeInTheDocument()
    expect(screen.queryByRole('complementary', { name: /sources/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('complementary', { name: /sources loading/i })).not.toBeInTheDocument()
    expect(screen.queryByText(/loading chat/i)).not.toBeInTheDocument()
  })

  it('renders conversation rail skeleton rows during the first conversation load', () => {
    chatMocks.conversationsLoading = true

    renderChat()

    expect(screen.getAllByTestId('chat-history-skeleton-row')).toHaveLength(5)
    expect(screen.getByRole('heading', { name: /ask playbookai/i })).toBeInTheDocument()
  })

  it('keeps conversation history visible with a quiet refresh indicator during background fetches', () => {
    chatMocks.conversations = [summary('c1', 'NIL disclosure window', today)]
    chatMocks.conversationsFetching = true

    renderChat()

    expect(screen.getByRole('button', { name: /nil disclosure window/i })).toBeInTheDocument()
    expect(screen.getByText(/refreshing chats/i)).toBeInTheDocument()
    expect(screen.queryByTestId('chat-history-skeleton-row')).not.toBeInTheDocument()
  })

  it('renders the active thread skeleton while conversation detail resolves', () => {
    const todayConversation = summary('c1', 'NIL disclosure window', today)
    chatMocks.conversations = [todayConversation]
    chatMocks.detailLoading = true
    useUIStore.setState({ activeConversationId: 'c1', sourcesOpen: true })

    renderChat()

    expect(screen.getByTestId('chat-thread-skeleton')).toBeInTheDocument()
    expect(screen.getByText(/loading conversation/i)).toBeInTheDocument()
  })

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

  it('uses existing app typography classes for chat controls and history', () => {
    const todayConversation = summary('c1', 'NIL disclosure window', today)
    chatMocks.conversations = [todayConversation]
    chatMocks.details = new Map([['c1', detail(todayConversation)]])

    renderChat()

    const newChatAction = screen.getAllByRole('button', { name: /new chat/i })[0]
    const historyRow = screen.getByRole('button', { name: /nil disclosure window/i })
    const groupLabel = screen.getByText('Today')
    const composer = screen.getByLabelText(/message playbook/i)

    expect(newChatAction).toHaveClass('pb-ui-sm')
    expect(historyRow).toHaveClass('pb-ui-sm')
    expect(groupLabel).toHaveClass('pb-ui-xs')
    expect(composer).toHaveClass('text-sm')
    expect(newChatAction).not.toHaveClass('text-sm')
    expect(historyRow).not.toHaveClass('text-[13.5px]')
    expect(composer).not.toHaveClass('text-[15px]')
  })

  it('submits non-empty composer text while preserving multiline drafts', async () => {
    renderChat()
    const textarea = screen.getByLabelText(/message playbook/i)

    await userEvent.type(textarea, 'Can I travel?')
    await userEvent.click(screen.getByRole('button', { name: /^ask$/i }))

    expect(screen.getByText('Can I travel?')).toBeInTheDocument()
    expect(screen.getByText(/thinking/i)).toBeInTheDocument()
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

    expect(screen.queryByRole('menuitem', { name: /admin dashboard/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('menuitem', { name: /chat workspace/i })).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('menuitem', { name: /settings/i }))

    expect(screen.getByRole('dialog', { name: /settings/i })).toBeInTheDocument()

    await userEvent.keyboard('{Escape}')
    await userEvent.click(screen.getByRole('button', { name: /jordan mitchell account menu/i }))
    await userEvent.click(screen.getByRole('menuitem', { name: /sign out/i }))

    expect(chatMocks.logoutMutateAsync).toHaveBeenCalledOnce()
  })

  it('shows only the admin dashboard switcher from the chat account menu for admins', async () => {
    currentUser.role = 'admin'
    renderChat()

    await userEvent.click(screen.getByRole('button', { name: /jordan mitchell account menu/i }))

    expect(screen.getByRole('menuitem', { name: /admin dashboard/i })).toBeInTheDocument()
    expect(screen.queryByRole('menuitem', { name: /chat workspace/i })).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('menuitem', { name: /admin dashboard/i }))

    expect(chatMocks.routerPush).toHaveBeenCalledWith('/admin')
  })
})
