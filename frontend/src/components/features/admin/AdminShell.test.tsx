import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AdminShell } from '@/src/components/features/admin/AdminShell'
import { useUIStore } from '@/src/lib/store/uiStore'

const adminRouterMocks = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn(),
}))

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: adminRouterMocks.push, replace: adminRouterMocks.replace }),
}))

const currentUser = vi.hoisted(() => ({
  email: 'j.mitchell@okstate.edu',
  id: 'u1',
  name: 'Jordan Mitchell',
  role: 'athlete',
}))

const adminUsers = vi.hoisted(() => [
  {
    id: 'u1',
    organization_id: 'org-1',
    name: 'Jordan Mitchell',
    email: 'j.mitchell@okstate.edu',
    role: 'super_admin',
    profile_complete: true,
    is_active: true,
  },
  {
    id: 'u2',
    organization_id: 'org-1',
    name: 'Maya Carter',
    email: 'm.carter@okstate.edu',
    role: 'admin',
    profile_complete: true,
    is_active: true,
  },
  {
    id: 'u3',
    organization_id: 'org-1',
    name: 'Ray Diaz',
    email: 'r.diaz@okstate.edu',
    role: 'admin',
    profile_complete: true,
    is_active: true,
  },
  {
    id: 'u4',
    organization_id: 'org-1',
    name: 'Tom Becker',
    email: 't.becker@okstate.edu',
    role: 'athlete',
    profile_complete: true,
    is_active: true,
  },
  {
    id: 'u5',
    organization_id: 'org-1',
    name: 'Priya Shah',
    email: 'p.shah@okstate.edu',
    role: 'athlete',
    profile_complete: true,
    is_active: true,
  },
  {
    id: 'u6',
    organization_id: 'org-1',
    name: 'Dana Lowe',
    email: 'd.lowe@okstate.edu',
    role: 'admin',
    profile_complete: true,
    is_active: true,
  },
] as const)

const updateRoleMutate = vi.hoisted(() => vi.fn())

vi.mock('@/src/hooks/useAuth', () => ({
  useCurrentUser: () => ({
    data: {
      id: currentUser.id,
      organization_id: 'org-1',
      name: currentUser.name,
      email: currentUser.email,
      role: currentUser.role,
      profile_complete: true,
      is_active: true,
    },
    isLoading: false,
  }),
  useLogout: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock('@/src/hooks/useAdmin', () => ({
  useAdminUsers: () => ({ data: adminUsers, isLoading: false }),
  useUpdateUserRole: () => ({ mutate: updateRoleMutate, isPending: false }),
  useAuditLogs: () => ({ data: new Array(16).fill(null).map((_, index) => ({ id: `audit-${index}` })), isLoading: false }),
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
    currentUser.id = 'u1'
    currentUser.name = 'Jordan Mitchell'
    currentUser.email = 'j.mitchell@okstate.edu'
    adminRouterMocks.push.mockClear()
    adminRouterMocks.replace.mockClear()
    updateRoleMutate.mockClear()
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

  it('shows only the chat workspace switcher from the admin account menu', async () => {
    currentUser.role = 'admin'
    renderAdmin()

    await userEvent.click(screen.getByRole('button', { name: /jordan mitchell account menu/i }))

    expect(screen.getByRole('menuitem', { name: /chat workspace/i })).toBeInTheDocument()
    expect(screen.queryByRole('menuitem', { name: /admin dashboard/i })).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('menuitem', { name: /chat workspace/i }))

    expect(adminRouterMocks.push).toHaveBeenCalledWith('/chat')
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

    expect(timeFilter).toHaveClass('pb-admin-header-control', 'pb-ui-sm')
    expect(regenerate).toHaveClass('pb-admin-header-control', 'pb-ui-sm')
    expect(explore).toHaveClass('pb-admin-header-control', 'pb-ui-sm')
    expect(timeFilter).not.toHaveClass('w-[156px]')
    expect(regenerate).not.toHaveClass('w-[156px]')
    expect(explore).not.toHaveClass('w-[156px]')
    expect(screen.getByRole('button', { name: /^Insights$/i })).toHaveClass('pb-admin-nav-item')
    expect(screen.getByRole('button', { name: /Knowledge base 1 failed document/i })).toHaveClass(
      'pb-admin-nav-item',
    )
    expect(screen.getByRole('button', { name: /Users & roles/i })).toHaveClass('pb-admin-nav-item')
    expect(screen.getByRole('button', { name: /^Insights$/i })).not.toHaveClass('text-[13.5px]')
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

  it('renders shared admin page headers for knowledge base and users', async () => {
    currentUser.role = 'super_admin'
    renderAdmin()

    await userEvent.click(screen.getByRole('button', { name: /knowledge base 1 failed document/i }))

    expect(screen.getByRole('heading', { name: 'Knowledge base' })).toHaveClass('pb-page-title')
    expect(screen.getByText(/1 document in knowledge base/i)).toHaveClass('pb-page-subtitle')

    await userEvent.click(screen.getByRole('button', { name: /users & roles/i }))

    expect(screen.getByRole('heading', { name: 'Users & roles' })).toHaveClass('pb-page-title')
    expect(screen.getByText(/6 users · 4 with admin access/i)).toHaveClass('pb-page-subtitle')
    expect(screen.queryByText(/audit events available/i)).not.toBeInTheDocument()
  })

  it('renders the Claude design Users & roles table and locked current user', async () => {
    currentUser.role = 'super_admin'
    useUIStore.setState({ adminTab: 'users' })
    renderAdmin()

    const usersTable = screen.getByLabelText(/users and roles table/i)

    expect(screen.queryByTestId('admin-page-toolbar')).not.toBeInTheDocument()
    expect(within(usersTable).getByPlaceholderText(/search users/i).closest('label')).toHaveClass('pb-admin-table-search')
    expect(within(usersTable).getByText('User')).toBeInTheDocument()
    expect(within(usersTable).getByText('Role')).toBeInTheDocument()
    expect(within(usersTable).getByText('Jordan Mitchell')).toBeInTheDocument()
    expect(within(usersTable).getByText('j.mitchell@okstate.edu')).toBeInTheDocument()
    expect(within(usersTable).getByText('YOU')).toBeInTheDocument()
    expect(within(usersTable).getByText('Locked')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /change role for jordan mitchell/i })).not.toBeInTheDocument()
    expect(within(usersTable).getByText('Super admin')).toBeInTheDocument()
    expect(within(usersTable).getAllByText('Admin')).toHaveLength(3)
    expect(within(usersTable).getAllByText('Athlete')).toHaveLength(2)
  })

  it('uses compact admin typography for users table actions and menus', async () => {
    currentUser.role = 'super_admin'
    useUIStore.setState({ adminTab: 'users' })
    renderAdmin()

    const changeRole = screen.getByRole('button', { name: /change role for tom becker/i })
    expect(changeRole).toHaveClass('pb-admin-table-action')
    expect(changeRole).not.toHaveClass('text-sm', 'text-base', 'text-[12.5px]')

    await userEvent.click(changeRole)

    expect(screen.getByRole('menu')).toHaveClass('pb-admin-menu')
    expect(screen.getByText('Set as athlete')).toHaveClass('pb-admin-menu-item')
    expect(screen.getByText('Promote to admin')).toHaveClass('pb-admin-menu-item')
  })

  it('filters users by name and email', async () => {
    currentUser.role = 'super_admin'
    useUIStore.setState({ adminTab: 'users' })
    renderAdmin()

    const usersTable = screen.getByLabelText(/users and roles table/i)
    const search = within(usersTable).getByPlaceholderText(/search users/i)

    await userEvent.type(search, 'ray')

    expect(screen.getByText('Ray Diaz')).toBeInTheDocument()
    expect(screen.queryByText('Maya Carter')).not.toBeInTheDocument()

    await userEvent.clear(search)
    await userEvent.type(search, 'p.shah')

    expect(screen.getByText('Priya Shah')).toBeInTheDocument()
    expect(screen.queryByText('Ray Diaz')).not.toBeInTheDocument()

    await userEvent.clear(search)
    await userEvent.type(search, 'no match')

    expect(screen.getByText(/no users match that search/i)).toBeInTheDocument()
  })

  it('changes roles through the Radix role menu', async () => {
    currentUser.role = 'super_admin'
    useUIStore.setState({ adminTab: 'users' })
    renderAdmin()

    await userEvent.click(screen.getByRole('button', { name: /change role for tom becker/i }))

    expect(screen.getByText('Set as athlete')).toHaveAttribute('data-disabled')

    await userEvent.click(screen.getByText('Promote to admin'))

    expect(updateRoleMutate).toHaveBeenCalledWith({ userId: 'u4', role: 'admin' })
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
