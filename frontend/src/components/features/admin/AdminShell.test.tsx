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
  isLoading: false,
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
const retryDocumentMutate = vi.hoisted(() => vi.fn())
const deleteDocumentMutate = vi.hoisted(() => vi.fn())
const updateDocumentMutate = vi.hoisted(() => vi.fn())
const uploadDocumentMutate = vi.hoisted(() => vi.fn())
const adminQueryState = vi.hoisted(() => ({
  kbError: false,
  kbFetching: false,
  kbLoading: false,
  usersError: false,
  usersFetching: false,
  usersLoading: false,
}))
const kbDocuments = vi.hoisted(() => [
  {
    id: 'doc-nil-policy',
    organization_id: 'org-1',
    uploaded_by: 'u1',
    title: 'NIL_POLICY_2025.PDF',
    filename: 'NIL_POLICY_2025.PDF',
    content_type: 'application/pdf',
    size_bytes: 1_800_000,
    processing_status: 'ready',
    failure_reason: null,
    visibility_policy: { scope: 'all_athletes' },
    metadata_tags: { collection: 'compliance', topics: ['NIL', 'Compliance'] },
    source_date: '2026-03-01',
    is_official: true,
    priority: 3,
    kb_service_document_id: 'kb-doc-1',
    created_at: '2026-03-14T12:00:00Z',
    updated_at: '2026-03-14T12:00:00Z',
  },
  {
    id: 'doc-recruiting',
    organization_id: 'org-1',
    uploaded_by: 'u1',
    title: 'RECRUITING_DEAD_PERIODS.PDF',
    filename: 'RECRUITING_DEAD_PERIODS.PDF',
    content_type: 'application/pdf',
    size_bytes: 1_100_000,
    processing_status: 'failed',
    failure_reason: 'Scanned PDF - no extractable text layer.',
    visibility_policy: { scope: 'all_athletes' },
    metadata_tags: { collection: 'compliance', topics: ['Recruiting'] },
    source_date: null,
    is_official: false,
    priority: 3,
    kb_service_document_id: null,
    created_at: '2026-06-03T12:00:00Z',
    updated_at: '2026-06-03T12:00:00Z',
  },
  {
    id: 'doc-travel',
    organization_id: 'org-1',
    uploaded_by: 'u2',
    title: 'PER_DIEM_RATES.XLSX',
    filename: 'PER_DIEM_RATES.XLSX',
    content_type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    size_bytes: 88_000,
    processing_status: 'ready',
    failure_reason: null,
    visibility_policy: { scope: 'all_athletes' },
    metadata_tags: { collection: 'travel', topics: ['Travel'] },
    source_date: '2026-06-01',
    is_official: true,
    priority: 1,
    kb_service_document_id: 'kb-doc-3',
    created_at: '2026-06-01T12:00:00Z',
    updated_at: '2026-06-01T12:00:00Z',
  },
] as Array<Record<string, unknown>>)

vi.mock('@/src/hooks/useAuth', () => ({
  useCurrentUser: () => ({
    data: currentUser.isLoading
      ? undefined
      : {
          id: currentUser.id,
          organization_id: 'org-1',
          name: currentUser.name,
          email: currentUser.email,
          role: currentUser.role,
          profile_complete: true,
          is_active: true,
        },
    isLoading: currentUser.isLoading,
  }),
  useLogout: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock('@/src/hooks/useAdmin', () => ({
  useAdminUsers: () => ({
    data: adminQueryState.usersLoading ? undefined : adminUsers,
    isError: adminQueryState.usersError,
    isFetching: adminQueryState.usersFetching,
    isLoading: adminQueryState.usersLoading,
  }),
  useUpdateUserRole: () => ({ mutate: updateRoleMutate, isPending: false }),
  useAuditLogs: () => ({ data: new Array(16).fill(null).map((_, index) => ({ id: `audit-${index}` })), isLoading: false }),
}))

vi.mock('@/src/hooks/useKBDocuments', () => ({
  useKBDocuments: () => ({
    data: adminQueryState.kbLoading ? undefined : kbDocuments,
    isError: adminQueryState.kbError,
    isFetching: adminQueryState.kbFetching,
    isLoading: adminQueryState.kbLoading,
  }),
  useUploadKBDocument: () => ({ mutateAsync: uploadDocumentMutate, isPending: false }),
  useRetryKBDocument: () => ({ mutate: retryDocumentMutate, isPending: false }),
  useDeleteKBDocument: () => ({ mutate: deleteDocumentMutate, isPending: false }),
  useUpdateKBDocumentMetadata: () => ({ mutate: updateDocumentMutate, isPending: false }),
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
    currentUser.isLoading = false
    currentUser.name = 'Jordan Mitchell'
    currentUser.email = 'j.mitchell@okstate.edu'
    adminQueryState.kbError = false
    adminQueryState.kbFetching = false
    adminQueryState.kbLoading = false
    adminQueryState.usersError = false
    adminQueryState.usersFetching = false
    adminQueryState.usersLoading = false
    adminRouterMocks.push.mockClear()
    adminRouterMocks.replace.mockClear()
    updateRoleMutate.mockClear()
    retryDocumentMutate.mockClear()
    deleteDocumentMutate.mockClear()
    updateDocumentMutate.mockClear()
    uploadDocumentMutate.mockClear()
    uploadDocumentMutate.mockResolvedValue(kbDocuments[0])
    kbDocuments.splice(0, kbDocuments.length, ...[
      {
        id: 'doc-nil-policy',
        organization_id: 'org-1',
        uploaded_by: 'u1',
        title: 'NIL_POLICY_2025.PDF',
        filename: 'NIL_POLICY_2025.PDF',
        content_type: 'application/pdf',
        size_bytes: 1_800_000,
        processing_status: 'ready',
        failure_reason: null,
        visibility_policy: { scope: 'all_athletes' },
        metadata_tags: { collection: 'compliance', topics: ['NIL', 'Compliance'] },
        source_date: '2026-03-01',
        is_official: true,
        priority: 3,
        kb_service_document_id: 'kb-doc-1',
        created_at: '2026-03-14T12:00:00Z',
        updated_at: '2026-03-14T12:00:00Z',
      },
      {
        id: 'doc-recruiting',
        organization_id: 'org-1',
        uploaded_by: 'u1',
        title: 'RECRUITING_DEAD_PERIODS.PDF',
        filename: 'RECRUITING_DEAD_PERIODS.PDF',
        content_type: 'application/pdf',
        size_bytes: 1_100_000,
        processing_status: 'failed',
        failure_reason: 'Scanned PDF - no extractable text layer.',
        visibility_policy: { scope: 'all_athletes' },
        metadata_tags: { collection: 'compliance', topics: ['Recruiting'] },
        source_date: null,
        is_official: false,
        priority: 3,
        kb_service_document_id: null,
        created_at: '2026-06-03T12:00:00Z',
        updated_at: '2026-06-03T12:00:00Z',
      },
      {
        id: 'doc-travel',
        organization_id: 'org-1',
        uploaded_by: 'u2',
        title: 'PER_DIEM_RATES.XLSX',
        filename: 'PER_DIEM_RATES.XLSX',
        content_type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        size_bytes: 88_000,
        processing_status: 'ready',
        failure_reason: null,
        visibility_policy: { scope: 'all_athletes' },
        metadata_tags: { collection: 'travel', topics: ['Travel'] },
        source_date: '2026-06-01',
        is_official: true,
        priority: 1,
        kb_service_document_id: 'kb-doc-3',
        created_at: '2026-06-01T12:00:00Z',
        updated_at: '2026-06-01T12:00:00Z',
      },
    ])
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

  it('renders a workspace skeleton while admin auth resolves', () => {
    currentUser.isLoading = true

    renderAdmin()

    expect(screen.getByTestId('admin-workspace-skeleton')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Insights' })).toBeInTheDocument()
    expect(screen.getByText('AI summary')).toBeInTheDocument()
    expect(screen.getByText('Last 7 days')).toBeInTheDocument()
    expect(screen.queryByText(/ai generated insights from user queries/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/users & roles/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/loading admin/i)).not.toBeInTheDocument()
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

  it('opens admin settings without security and SSO options', async () => {
    currentUser.role = 'admin'
    renderAdmin()

    await userEvent.click(screen.getByRole('button', { name: /jordan mitchell account menu/i }))
    await userEvent.click(screen.getByRole('menuitem', { name: /settings/i }))

    const dialog = screen.getByRole('dialog', { name: /settings/i })

    expect(dialog).toBeInTheDocument()
    expect(within(dialog).queryByRole('tab', { name: /security & sso/i })).not.toBeInTheDocument()

    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('dialog', { name: /settings/i })).not.toBeInTheDocument()
  })

  it('renders the Claude design Insights dashboard hierarchy for admins', () => {
    currentUser.role = 'super_admin'
    renderAdmin()

    expect(screen.getByRole('heading', { name: 'Insights' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Insights' })).toHaveClass('pb-page-title')
    expect(screen.getByText(/AI generated insights from user queries/i)).toBeInTheDocument()
    expect(screen.getByText(/AI generated insights from user queries/i)).toHaveClass('pb-page-subtitle')
    const timeFilter = screen.getByRole('button', { name: /Last 7 days/i })
    const regenerate = screen.getByRole('button', { name: /Regenerate/i })
    const explore = screen.getByRole('button', { name: /Explore with AI/i })

    expect(timeFilter).toHaveClass('pb-admin-header-control', 'pb-ui-sm')
    expect(regenerate).toHaveClass('pb-admin-header-control', 'pb-ui-sm')
    expect(explore).toHaveClass('pb-admin-header-control', 'pb-ui-sm')
    expect(screen.getByRole('button', { name: /^Insights$/i })).toHaveClass('pb-admin-nav-item')
    expect(screen.getByRole('button', { name: /^Insights$/i })).toHaveClass('pb-focus-control')
    expect(screen.getByRole('button', { name: /Knowledge base 1 failed document/i })).toHaveClass(
      'pb-admin-nav-item',
    )
    expect(screen.getByRole('button', { name: /Users & roles/i })).toHaveClass('pb-admin-nav-item')
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
    expect(screen.getByText(/3 documents across 4 collections/i)).toHaveClass('pb-page-subtitle')

    await userEvent.click(screen.getByRole('button', { name: /users & roles/i }))

    expect(screen.getByRole('heading', { name: 'Users & roles' })).toHaveClass('pb-page-title')
    expect(screen.getByText(/6 users · 4 with admin access/i)).toHaveClass('pb-page-subtitle')
    expect(screen.queryByText(/audit events available/i)).not.toBeInTheDocument()
  })

  it('renders the collection-first knowledge base grid with design counts', async () => {
    currentUser.role = 'super_admin'
    useUIStore.setState({ adminTab: 'kb' })
    renderAdmin()

    expect(screen.getByRole('heading', { name: 'Knowledge base' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /New collection/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Compliance & NIL collection/i })).toHaveTextContent('2 documents')
    expect(screen.getByRole('button', { name: /Compliance & NIL collection/i })).toHaveTextContent('1 needs attention')
    expect(screen.getByRole('button', { name: /Team Travel collection/i })).toHaveTextContent('1 document')
    expect(screen.getByRole('button', { name: /Team Travel collection/i })).toHaveTextContent('All ready')
    expect(screen.getByRole('button', { name: /Academic Services collection/i })).toHaveTextContent('No documents yet')
    expect(screen.getByRole('button', { name: /Donor Relations collection/i })).toHaveTextContent('No documents yet')
  })

  it('renders collection skeletons for the first knowledge-base load', () => {
    currentUser.role = 'super_admin'
    adminQueryState.kbLoading = true
    useUIStore.setState({ adminTab: 'kb' })

    renderAdmin()

    expect(screen.getByTestId('admin-kb-skeleton')).toBeInTheDocument()
    expect(screen.getAllByTestId('admin-kb-collection-skeleton')).toHaveLength(4)
    expect(screen.queryByText(/0 documents across 4 collections/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/^No documents yet\.$/i)).not.toBeInTheDocument()
  })

  it('keeps knowledge-base collections visible during background refreshes', () => {
    currentUser.role = 'super_admin'
    adminQueryState.kbFetching = true
    useUIStore.setState({ adminTab: 'kb' })

    renderAdmin()

    expect(screen.getByRole('button', { name: /Compliance & NIL collection/i })).toBeInTheDocument()
    expect(screen.getByText(/refreshing knowledge base/i)).toBeInTheDocument()
    expect(screen.queryByTestId('admin-kb-skeleton')).not.toBeInTheDocument()
  })

  it('uses info-tone indicators for queued and processing documents', async () => {
    currentUser.role = 'super_admin'
    kbDocuments.push({
      id: 'doc-processing',
      organization_id: 'org-1',
      uploaded_by: 'u1',
      title: 'NIL_AGENCY_GUIDE_2027.DOCX',
      filename: 'NIL_AGENCY_GUIDE_2027.DOCX',
      content_type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      size_bytes: 640_000,
      processing_status: 'uploaded',
      failure_reason: null,
      visibility_policy: { scope: 'all_athletes' },
      metadata_tags: { collection: 'travel', topics: ['Travel'] },
      source_date: null,
      is_official: false,
      priority: 1,
      kb_service_document_id: null,
      created_at: '2026-06-03T12:00:00Z',
      updated_at: '2026-06-03T12:00:00Z',
    })
    useUIStore.setState({ adminTab: 'kb' })

    renderAdmin()

    expect(screen.getByRole('button', { name: /Team Travel collection/i })).toHaveTextContent('1 processing')

    await userEvent.click(screen.getByRole('button', { name: /Team Travel collection/i }))

    expect(screen.getByText('Queued').closest('span')).toHaveClass('text-info')
  })

  it('uploads a KB document with local progress and queued status', async () => {
    currentUser.role = 'super_admin'
    useUIStore.setState({ adminTab: 'kb' })
    uploadDocumentMutate.mockImplementation(async (request) => {
      request.onProgress?.({ loaded: 5, percent: 50, total: 10 })
      return { ...kbDocuments[0], id: 'doc-uploaded', title: request.file.name }
    })
    renderAdmin()

    await userEvent.click(screen.getByRole('button', { name: /Compliance & NIL collection/i }))
    await userEvent.upload(
      screen.getByLabelText(/upload document file/i),
      new File(['hello'], 'athlete-handbook.pdf', { type: 'application/pdf' }),
    )

    expect(uploadDocumentMutate).toHaveBeenCalledWith(
      expect.objectContaining({
        file: expect.objectContaining({ name: 'athlete-handbook.pdf' }),
        metadata_tags: expect.objectContaining({ collection: 'compliance' }),
        onProgress: expect.any(Function),
      }),
    )
    expect(await screen.findByText('athlete-handbook.pdf')).toBeInTheDocument()
    expect(await screen.findByText('Queued')).toBeInTheDocument()
  })

  it('shows a safe admin upload failure and retries with a fresh intent', async () => {
    currentUser.role = 'super_admin'
    useUIStore.setState({ adminTab: 'kb' })
    uploadDocumentMutate.mockRejectedValueOnce(new Error('File upload failed before Playbook received it.'))
    uploadDocumentMutate.mockResolvedValueOnce(kbDocuments[0])
    renderAdmin()

    await userEvent.click(screen.getByRole('button', { name: /Compliance & NIL collection/i }))
    await userEvent.upload(
      screen.getByLabelText(/upload document file/i),
      new File(['hello'], 'retry-me.pdf', { type: 'application/pdf' }),
    )

    expect(await screen.findByText('File upload failed before Playbook received it.')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /try again/i }))

    expect(uploadDocumentMutate).toHaveBeenCalledTimes(2)
  })

  it('keeps collections visible when there are no documents', () => {
    currentUser.role = 'super_admin'
    kbDocuments.splice(0, kbDocuments.length)
    useUIStore.setState({ adminTab: 'kb' })
    renderAdmin()

    expect(screen.getByText(/0 documents across 4 collections/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Compliance & NIL collection/i })).toHaveTextContent('No documents yet')
    expect(screen.getByRole('button', { name: /Team Travel collection/i })).toHaveTextContent('No documents yet')
    expect(screen.queryByText(/^No documents yet\.$/i)).not.toBeInTheDocument()
  })

  it('shows read-only collection management for department admins', () => {
    currentUser.role = 'admin'
    useUIStore.setState({ adminTab: 'kb' })
    renderAdmin()

    expect(screen.getByText(/Managed by super admins/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /New collection/i })).not.toBeInTheDocument()
  })

  it('opens collection detail and routes document actions through KB mutations', async () => {
    currentUser.role = 'super_admin'
    useUIStore.setState({ adminTab: 'kb' })
    renderAdmin()

    await userEvent.click(screen.getByRole('button', { name: /Compliance & NIL collection/i }))

    expect(screen.getByRole('heading', { name: 'Compliance & NIL' })).toBeInTheDocument()
    expect(screen.getByText(/2 documents · grounds athlete answers/i)).toBeInTheDocument()
    expect(screen.getByText('NIL_POLICY_2025.PDF')).toBeInTheDocument()
    expect(screen.getByText('RECRUITING_DEAD_PERIODS.PDF')).toBeInTheDocument()
    expect(screen.getByText(/Scanned PDF - no extractable text layer/i)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /Retry RECRUITING_DEAD_PERIODS.PDF/i }))
    expect(retryDocumentMutate).toHaveBeenCalledWith('doc-recruiting')

    await userEvent.click(screen.getByRole('button', { name: /Actions for RECRUITING_DEAD_PERIODS.PDF/i }))
    await userEvent.click(screen.getByRole('menuitem', { name: /Mark official/i }))
    expect(updateDocumentMutate).toHaveBeenCalledWith({ documentId: 'doc-recruiting', isOfficial: true })

    await userEvent.click(screen.getByRole('button', { name: /Actions for RECRUITING_DEAD_PERIODS.PDF/i }))
    await userEvent.click(screen.getByRole('menuitem', { name: /Delete \/ archive/i }))
    expect(deleteDocumentMutate).toHaveBeenCalledWith('doc-recruiting')

    await userEvent.click(screen.getByRole('button', { name: /All collections/i }))
    expect(screen.getByRole('heading', { name: 'Knowledge base' })).toBeInTheDocument()
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
    expect(within(usersTable).getByText('You')).toBeInTheDocument()
    expect(within(usersTable).getByText('Locked')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /change role for jordan mitchell/i })).not.toBeInTheDocument()
    expect(within(usersTable).getByText('Super admin')).toBeInTheDocument()
    expect(within(usersTable).getAllByText('Admin')).toHaveLength(3)
    expect(within(usersTable).getAllByText('Athlete')).toHaveLength(2)
  })

  it('renders user table skeletons during the first users load', () => {
    currentUser.role = 'super_admin'
    adminQueryState.usersLoading = true
    useUIStore.setState({ adminTab: 'users' })

    renderAdmin()

    expect(screen.getByTestId('admin-users-skeleton')).toBeInTheDocument()
    expect(screen.getByText('Search users...')).toBeInTheDocument()
    expect(screen.getByText('User')).toBeInTheDocument()
    expect(screen.getByText('Role')).toBeInTheDocument()
    expect(screen.queryByText(/0 users/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/no users returned yet/i)).not.toBeInTheDocument()
  })

  it('keeps user rows visible during background users refreshes', () => {
    currentUser.role = 'super_admin'
    adminQueryState.usersFetching = true
    useUIStore.setState({ adminTab: 'users' })

    renderAdmin()

    expect(screen.getAllByText('Jordan Mitchell')).not.toHaveLength(0)
    expect(screen.getByText(/refreshing users/i)).toBeInTheDocument()
    expect(screen.queryByTestId('admin-users-skeleton')).not.toBeInTheDocument()
  })

  it('uses compact admin typography for users table actions and menus', async () => {
    currentUser.role = 'super_admin'
    useUIStore.setState({ adminTab: 'users' })
    renderAdmin()

    const changeRole = screen.getByRole('button', { name: /change role for tom becker/i })
    expect(changeRole).toHaveClass('pb-admin-table-action')
    expect(changeRole).toHaveClass('pb-focus-control')

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
