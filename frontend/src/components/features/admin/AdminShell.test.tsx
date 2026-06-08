import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AdminShell } from '@/src/components/features/admin/AdminShell'
import { useUIStore } from '@/src/lib/store/uiStore'

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}))

const currentUser = vi.hoisted(() => ({
  role: 'athlete',
}))

vi.mock('@/src/hooks/useAuth', () => ({
  useCurrentUser: () => ({
    data: {
      name: 'Jordan',
      email: 'jordan@example.com',
      role: currentUser.role,
      profile_complete: true,
    },
    isLoading: false,
  }),
  useLogout: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock('@/src/hooks/useAdmin', () => ({
  useAdminUsers: () => ({ data: [], isLoading: false }),
  useUpdateUserRole: () => ({ mutate: vi.fn(), isPending: false }),
  useAuditLogs: () => ({ data: [], isLoading: false }),
}))

vi.mock('@/src/hooks/useKBDocuments', () => ({
  useKBDocuments: () => ({
    data: [
      {
        id: 'doc-failed',
        title: 'RECRUITING_DEAD_PERIODS.PDF',
        processing_status: 'failed',
        is_official: false,
        failure_reason: 'Scanned PDF',
      },
    ],
    isLoading: false,
  }),
  useUploadKBDocument: () => ({ mutate: vi.fn(), isPending: false }),
  useRetryKBDocument: () => ({ mutate: vi.fn(), isPending: false }),
  useDeleteKBDocument: () => ({ mutate: vi.fn(), isPending: false }),
  useUpdateKBDocumentMetadata: () => ({ mutate: vi.fn(), isPending: false }),
}))

function renderAdmin() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <AdminShell />
    </QueryClientProvider>,
  )
}

describe('AdminShell', () => {
  beforeEach(() => {
    useUIStore.setState({
      adminTab: 'insights',
      adminChatOpen: false,
      adminTimeWindow: '7d',
      adminInsightStatus: 'completed',
      adminChatMessages: [],
    })
  })

  it('denies athlete access', () => {
    currentUser.role = 'athlete'
    renderAdmin()

    expect(screen.getByRole('heading', { name: /admins only/i })).toBeInTheDocument()
  })

  it('shows super-admin-only users navigation for super admins', () => {
    currentUser.role = 'super_admin'
    renderAdmin()

    expect(screen.getByRole('button', { name: /users & roles/i })).toBeInTheDocument()
  })

  it('renders the Claude design Insights dashboard hierarchy for admins', () => {
    currentUser.role = 'super_admin'
    renderAdmin()

    expect(screen.getByRole('heading', { name: 'Insights' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Insights' })).toHaveClass('pb-page-title')
    expect(screen.getByRole('heading', { name: 'Insights' })).not.toHaveClass('text-[32px]')
    expect(screen.getByText(/AI generated insights from user queries/i)).toBeInTheDocument()
    expect(screen.getByText(/AI generated insights from user queries/i)).toHaveClass('pb-page-subtitle')
    const timeFilter = screen.getByRole('button', { name: /Last 7 days/i })
    const regenerate = screen.getByRole('button', { name: /Regenerate/i })
    const explore = screen.getByRole('button', { name: /Explore with AI/i })

    expect(timeFilter).toHaveClass('h-9', 'w-[156px]', 'pb-ui-sm', 'justify-center')
    expect(regenerate).toHaveClass('h-9', 'w-[156px]', 'pb-ui-sm', 'justify-center')
    expect(explore).toHaveClass('h-9', 'w-[156px]', 'pb-ui-sm', 'justify-center')
    expect(screen.getByText(/AI summary/i)).toBeInTheDocument()
    expect(screen.getByText(/NIL disclosure timing is the clearest support gap/i)).toBeInTheDocument()
    expect(screen.getByText(/NIL questions/i)).toBeInTheDocument()
    expect(screen.getByText(/High-risk flags/i)).toBeInTheDocument()
    expect(screen.getByText(/Common topics/i)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /^Risk flags$/i })).toBeInTheDocument()
    expect(screen.getByText(/Query volume/i)).toBeInTheDocument()
    expect(screen.getByText(/128 this week/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Knowledge base 1 failed document/i })).toBeInTheDocument()
    expect(screen.queryByText(/Fixture-backed until Phase 4 APIs land/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/Grounded rate/i)).not.toBeInTheDocument()
  })

  it('expands insight details and opens the analytics chat side panel', async () => {
    currentUser.role = 'super_admin'
    renderAdmin()

    await userEvent.click(screen.getByRole('button', { name: /Show details/i }))

    expect(screen.getByText(/Recommended focus/i)).toBeInTheDocument()
    expect(screen.getByText(/Clarify NIL disclosure timing/i)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /Explore with AI/i }))

    expect(screen.getByRole('complementary', { name: /Analytics AI Agent/i })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /What are athletes most confused about this week/i }))

    expect(await screen.findByText(/The clearest confusion this week is NIL disclosure timing/i)).toBeInTheDocument()
  })
})
