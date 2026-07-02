import { beforeEach, describe, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AdminShell } from '@/src/components/features/admin/AdminShell'
import { useUIStore } from '@/src/lib/store/uiStore'

const globalsCss = readFileSync(resolve(process.cwd(), 'src/app/globals.css'), 'utf8')

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
const updateDocumentMutateAsync = vi.hoisted(() => vi.fn())
const uploadDocumentMutate = vi.hoisted(() => vi.fn())
const createCollectionMutateAsync = vi.hoisted(() => vi.fn())
const deleteCollectionMutateAsync = vi.hoisted(() => vi.fn())
const createMetadataTagMutateAsync = vi.hoisted(() => vi.fn())
const updateMetadataTagMutateAsync = vi.hoisted(() => vi.fn())
const archiveMetadataTagMutateAsync = vi.hoisted(() => vi.fn())
const unarchiveMetadataTagMutateAsync = vi.hoisted(() => vi.fn())
const deleteMetadataTagPermanentlyMutateAsync = vi.hoisted(() => vi.fn())
const createAdminChatSessionMutateAsync = vi.hoisted(() => vi.fn())
const submitAdminChatMessageMutateAsync = vi.hoisted(() => vi.fn())
const startAdminChatStream = vi.hoisted(() => vi.fn())
const stopAdminChatStream = vi.hoisted(() => vi.fn())
const createDashboardInsightRunMutateAsync = vi.hoisted(() => vi.fn())
const adminAnalyticsHookCalls = vi.hoisted(
  () =>
    [] as Array<{
      hook: string
      enabled: boolean
      window?: string
      runId?: string | null
      page?: number
      filters?: {
        topic_labels?: string[]
        risk_labels?: string[]
      }
    }>,
)
const analyticsSummary = vi.hoisted(() => ({
  window_start: '2026-05-27T00:00:00Z',
  window_end: '2026-06-03T00:00:00Z',
  query_volume: 128,
  top_topics: [
    { label: 'nil', count: 48 },
    { label: 'compliance', count: 31 },
    { label: 'recruiting', count: 18 },
    { label: 'travel', count: 14 },
  ],
  unanswered_count: 12,
  risk_counts: { nil: 22, compliance: 14, recruiting: 3 },
  volume_series: [
    { date: '2026-05-27', total: 14, unanswered: 1 },
    { date: '2026-05-28', total: 19, unanswered: 2 },
    { date: '2026-05-29', total: 22, unanswered: 1 },
    { date: '2026-05-30', total: 12, unanswered: 0 },
    { date: '2026-05-31', total: 16, unanswered: 2 },
    { date: '2026-06-01', total: 27, unanswered: 3 },
    { date: '2026-06-02', total: 18, unanswered: 3 },
  ],
}))
const analyticsQueries = vi.hoisted(() => ({
  window_start: '2026-05-27T00:00:00Z',
  window_end: '2026-06-03T00:00:00Z',
  queries: [
    {
      message_id: 'message-1',
      anonymous_user_key: 'anon_1111',
      text: 'When do I disclose an NIL deal?',
      created_at: '2026-06-01T15:32:00Z',
      topic_labels: ['nil'],
      risk_labels: ['compliance'],
      response_status: 'complete',
      answer_type: 'grounded_answer',
      unanswered_reason: null,
    },
    {
      message_id: 'message-2',
      anonymous_user_key: 'anon_2222',
      text: 'Can recruiting staff text this prospect?',
      created_at: '2026-06-02T15:32:00Z',
      topic_labels: ['recruiting'],
      risk_labels: ['recruiting'],
      response_status: 'declined',
      answer_type: 'unsupported',
      unanswered_reason: 'unsupported',
    },
  ],
}))
const dashboardInsight = vi.hoisted(() => ({
  id: 'insight-1',
  run_id: 'run-1',
  summary:
    'NIL disclosure timing is the clearest support gap this week. Athletes repeatedly asked when in-kind benefits must be reported.',
  headline_cards: [
    {
      title: 'NIL disclosure timing',
      value: '18 questions',
      severity: 'medium' as const,
    },
    {
      title: 'Recruiting-contact rules',
      value: '6 high-risk questions',
      severity: 'high' as const,
    },
  ],
  topic_breakdown: [{ label: 'nil', count: 48 }],
  unanswered_questions: [
    {
      message_id: 'message-2',
      text: 'Can recruiting staff text this prospect?',
      reason: 'unsupported',
    },
  ],
  risk_breakdown: [{ label: 'recruiting', count: 3 }],
  recommended_attention_areas: [
    'Clarify NIL disclosure timing for in-kind benefits in athlete-facing guidance.',
    'Publish the NIL agency-registration deadline for the upcoming year.',
  ],
  source_message_ids: ['message-1', 'message-2'],
  generated_at: '2026-06-03T12:00:00Z',
}))
const adminAnalyticsState = vi.hoisted(() => ({
  currentInsight: null as typeof dashboardInsight | null,
  currentInsightError: false,
  currentInsightLoading: false,
  queries: analyticsQueries,
  queriesError: false,
  queriesLoading: false,
  run: null as {
    id: string
    organization_id: string
    requested_by: string | null
    trigger_type: 'manual' | 'nightly'
    status: 'pending' | 'processing' | 'completed' | 'failed'
    window_start: string
    window_end: string
    source_filters: Record<string, unknown>
    error_message: string | null
    created_at: string
    updated_at: string
    output: typeof dashboardInsight | null
  } | null,
  runError: false,
  runLoading: false,
  summary: analyticsSummary,
  summaryError: false,
  summaryLoading: false,
  createRunError: false,
  createRunPending: false,
}))
const adminChatMessages = vi.hoisted(
  () =>
    [] as Array<{
      id: string
      session_id: string
      role: 'user' | 'assistant'
      content: string
      status: 'complete' | 'streaming' | 'failed'
      references: Array<{ type: 'metric' | 'dashboard_insight' | 'query'; id: string }>
      metadata: Record<string, unknown>
      answer_type: 'analytics_answer' | 'refusal' | 'unsupported' | null
      created_at: string
    }>,
)
const adminQueryState = vi.hoisted(() => ({
  kbError: false,
  kbFetching: false,
  kbLoading: false,
  kbMetadataFetching: false,
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
    collection_id: 'collection-compliance',
    tag_slugs: ['nil', 'compliance'],
    visibility_policy: { scope: 'all_athletes' },
    metadata_tags: {
      collection: 'compliance',
      tag_slugs: ['nil', 'compliance'],
      tags: ['NIL', 'Compliance'],
      topics: ['Compliance & NIL', 'NIL', 'Compliance'],
    },
    source_date: '2026-03-01',
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
    collection_id: 'collection-compliance',
    tag_slugs: ['recruiting'],
    visibility_policy: { scope: 'all_athletes' },
    metadata_tags: {
      collection: 'compliance',
      tag_slugs: ['recruiting'],
      tags: ['Recruiting'],
      topics: ['Compliance & NIL', 'Recruiting'],
    },
    source_date: null,
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
    collection_id: 'collection-travel',
    tag_slugs: ['travel', 'old-policy'],
    visibility_policy: { scope: 'all_athletes' },
    metadata_tags: {
      collection: 'travel',
      tag_slugs: ['travel', 'old-policy'],
      tags: ['Travel', 'Old policy'],
      topics: ['Team Travel', 'Travel', 'Old policy'],
    },
    source_date: '2026-06-01',
    kb_service_document_id: 'kb-doc-3',
    created_at: '2026-06-01T12:00:00Z',
    updated_at: '2026-06-01T12:00:00Z',
  },
] as Array<Record<string, unknown>>)

const kbCollections = vi.hoisted(() => [
  {
    id: 'collection-compliance',
    organization_id: 'org-1',
    slug: 'compliance',
    title: 'Compliance & NIL',
    description: 'NIL, eligibility, and recruiting rules - kept current with department and NCAA policy.',
    icon: 'shield',
    sort_order: 10,
    is_active: true,
    created_at: '2026-06-29T12:00:00Z',
    updated_at: '2026-06-29T12:00:00Z',
  },
  {
    id: 'collection-travel',
    organization_id: 'org-1',
    slug: 'travel',
    title: 'Team Travel',
    description: 'Per-diem rates, charter logistics, and team hotel policy for every sport.',
    icon: 'plane',
    sort_order: 20,
    is_active: true,
    created_at: '2026-06-29T12:00:00Z',
    updated_at: '2026-06-29T12:00:00Z',
  },
  {
    id: 'collection-academics',
    organization_id: 'org-1',
    slug: 'academics',
    title: 'Academic Services',
    description: 'Study-hall rules, tutoring, and academic eligibility support.',
    icon: 'book-open',
    sort_order: 30,
    is_active: true,
    created_at: '2026-06-29T12:00:00Z',
    updated_at: '2026-06-29T12:00:00Z',
  },
  {
    id: 'collection-donor',
    organization_id: 'org-1',
    slug: 'donor',
    title: 'Donor Relations',
    description: 'Giving levels, suite benefits, and booster club answers for boosters.',
    icon: 'users',
    sort_order: 40,
    is_active: true,
    created_at: '2026-06-29T12:00:00Z',
    updated_at: '2026-06-29T12:00:00Z',
  },
] as Array<Record<string, unknown>>)

const kbMetadataTags = vi.hoisted(() => [
  {
    id: 'tag-nil',
    organization_id: 'org-1',
    slug: 'nil',
    label: 'NIL',
    sort_order: 10,
    is_active: true,
    created_at: '2026-06-29T12:00:00Z',
    updated_at: '2026-06-29T12:00:00Z',
  },
  {
    id: 'tag-compliance',
    organization_id: 'org-1',
    slug: 'compliance',
    label: 'Compliance',
    sort_order: 20,
    is_active: true,
    created_at: '2026-06-29T12:00:00Z',
    updated_at: '2026-06-29T12:00:00Z',
  },
  {
    id: 'tag-recruiting',
    organization_id: 'org-1',
    slug: 'recruiting',
    label: 'Recruiting',
    sort_order: 30,
    is_active: true,
    created_at: '2026-06-29T12:00:00Z',
    updated_at: '2026-06-29T12:00:00Z',
  },
  {
    id: 'tag-travel',
    organization_id: 'org-1',
    slug: 'travel',
    label: 'Travel',
    sort_order: 40,
    is_active: true,
    created_at: '2026-06-29T12:00:00Z',
    updated_at: '2026-06-29T12:00:00Z',
  },
  {
    id: 'tag-archived',
    organization_id: 'org-1',
    slug: 'legacy',
    label: 'Legacy',
    sort_order: 90,
    is_active: false,
    created_at: '2026-06-29T12:00:00Z',
    updated_at: '2026-06-29T12:00:00Z',
  },
  {
    id: 'tag-archived-used',
    organization_id: 'org-1',
    slug: 'old-policy',
    label: 'Old policy',
    sort_order: 100,
    is_active: false,
    created_at: '2026-06-29T12:00:00Z',
    updated_at: '2026-06-29T12:00:00Z',
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

vi.mock('@/src/hooks/useAdminChat', () => ({
  useAdminChatSessions: () => ({
    data: [],
    isError: false,
    isFetching: false,
    isLoading: false,
  }),
  useAdminChatSessionDetail: (sessionId: string | null) => ({
    data: sessionId
      ? {
          id: sessionId,
          title: 'Weekly NIL questions',
          status: 'active',
          context_window_start: null,
          context_window_end: null,
          last_message_at: null,
          created_at: '2026-06-29T12:00:00Z',
          updated_at: '2026-06-29T12:00:00Z',
          messages: adminChatMessages,
        }
      : undefined,
    isError: false,
    isFetching: false,
    isLoading: false,
  }),
  useCreateAdminChatSession: () => ({
    mutateAsync: createAdminChatSessionMutateAsync,
    isError: false,
    isPending: false,
  }),
  useSubmitAdminChatMessage: () => ({
    mutateAsync: submitAdminChatMessageMutateAsync,
    isError: false,
    isPending: false,
  }),
  useAdminChatMessageStream: () => ({
    start: startAdminChatStream,
    stop: stopAdminChatStream,
  }),
}))

vi.mock('@/src/hooks/useAdminAnalytics', () => ({
  QUERY_REVIEW_PAGE_SIZE: 10,
  normalizeAdminAnalyticsQueryFilters: (
    filters: { topic_labels?: string[]; risk_labels?: string[] } = {},
  ) => ({
    topic_labels: filters.topic_labels ?? [],
    risk_labels: filters.risk_labels ?? [],
  }),
  toManualRunWindow: () => ({
    window_start: '2026-06-01T00:00:00.000Z',
    window_end: '2026-06-08T00:00:00.000Z',
    source_filters: {},
  }),
  useAdminAnalyticsSummary: (window: string, enabled: boolean) => {
    adminAnalyticsHookCalls.push({ hook: 'summary', window, enabled })
    return {
      data: enabled ? adminAnalyticsState.summary : undefined,
      isError: adminAnalyticsState.summaryError,
      isFetching: false,
      isLoading: adminAnalyticsState.summaryLoading,
    }
  },
  useAdminAnalyticsQueries: (
    window: string,
    enabled: boolean,
    filters?: { topic_labels?: string[]; risk_labels?: string[] },
    page = 0,
  ) => {
    adminAnalyticsHookCalls.push({ hook: 'queries', window, enabled, filters, page })
    return {
      data: enabled ? adminAnalyticsState.queries : undefined,
      isError: adminAnalyticsState.queriesError,
      isFetching: false,
      isPlaceholderData: false,
      isLoading: adminAnalyticsState.queriesLoading,
    }
  },
  useCurrentDashboardInsight: (window: string, enabled: boolean) => {
    adminAnalyticsHookCalls.push({ hook: 'current', window, enabled })
    return {
      data: enabled ? adminAnalyticsState.currentInsight : undefined,
      isError: adminAnalyticsState.currentInsightError,
      isFetching: false,
      isLoading: adminAnalyticsState.currentInsightLoading,
    }
  },
  useDashboardInsightRun: (runId: string | null, enabled: boolean) => {
    adminAnalyticsHookCalls.push({ hook: 'run', runId, enabled })
    return {
      data: enabled ? adminAnalyticsState.run : undefined,
      isError: adminAnalyticsState.runError,
      isFetching: false,
      isLoading: adminAnalyticsState.runLoading,
    }
  },
  useCreateDashboardInsightRun: () => ({
    mutateAsync: createDashboardInsightRunMutateAsync,
    isError: adminAnalyticsState.createRunError,
    isPending: adminAnalyticsState.createRunPending,
  }),
}))

vi.mock('@/src/hooks/useKBDocuments', () => ({
  useKBCollections: () => ({
    data: adminQueryState.kbLoading ? undefined : kbCollections,
    isError: adminQueryState.kbError,
    isFetching: adminQueryState.kbFetching,
    isLoading: adminQueryState.kbLoading,
  }),
  useKBMetadataTags: () => ({
    data: kbMetadataTags,
    isError: false,
    isFetching: adminQueryState.kbMetadataFetching,
    isLoading: false,
  }),
  useKBDocuments: () => ({
    data: adminQueryState.kbLoading ? undefined : kbDocuments,
    isError: adminQueryState.kbError,
    isFetching: adminQueryState.kbFetching,
    isLoading: adminQueryState.kbLoading,
  }),
  useUploadKBDocument: () => ({ mutateAsync: uploadDocumentMutate, isPending: false }),
  useRetryKBDocument: () => ({ mutate: retryDocumentMutate, isPending: false }),
  useDeleteKBDocument: () => ({ mutate: deleteDocumentMutate, isPending: false }),
  useCreateKBCollection: () => ({ mutateAsync: createCollectionMutateAsync, isPending: false }),
  useDeleteKBCollection: () => ({ mutateAsync: deleteCollectionMutateAsync, isPending: false }),
  useCreateKBMetadataTag: () => ({ mutateAsync: createMetadataTagMutateAsync, isPending: false }),
  useUpdateKBMetadataTag: () => ({ mutateAsync: updateMetadataTagMutateAsync, isPending: false }),
  useArchiveKBMetadataTag: () => ({ mutateAsync: archiveMetadataTagMutateAsync, isPending: false }),
  useUnarchiveKBMetadataTag: () => ({ mutateAsync: unarchiveMetadataTagMutateAsync, isPending: false }),
  useDeleteKBMetadataTagPermanently: () => ({
    mutateAsync: deleteMetadataTagPermanentlyMutateAsync,
    isPending: false,
  }),
  useUpdateKBDocumentMetadata: () => ({
    mutate: updateDocumentMutate,
    mutateAsync: updateDocumentMutateAsync,
    isPending: false,
  }),
}))

function renderAdmin() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <AdminShell />
    </QueryClientProvider>,
  )
}

function getKnowledgeBaseUploadInput(): HTMLInputElement {
  const uploadInput = screen
    .getAllByLabelText(/Upload knowledge-base document/i)
    .find((element): element is HTMLInputElement => element instanceof HTMLInputElement)
  if (!uploadInput) throw new Error('Knowledge-base upload input not found')
  return uploadInput
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
    adminQueryState.kbMetadataFetching = false
    adminQueryState.usersError = false
    adminQueryState.usersFetching = false
    adminQueryState.usersLoading = false
    adminRouterMocks.push.mockClear()
    adminRouterMocks.replace.mockClear()
    updateRoleMutate.mockClear()
    retryDocumentMutate.mockClear()
    deleteDocumentMutate.mockClear()
    updateDocumentMutate.mockClear()
    updateDocumentMutateAsync.mockClear()
    updateDocumentMutateAsync.mockResolvedValue(kbDocuments[0])
    uploadDocumentMutate.mockClear()
    createCollectionMutateAsync.mockClear()
    createCollectionMutateAsync.mockResolvedValue({
      id: 'collection-sport-rules',
      organization_id: 'org-1',
      slug: 'sport-rules',
      title: 'Sport rules',
      description: 'Sport-specific rules and team policies.',
      icon: 'book-open',
      sort_order: 50,
      is_active: true,
      created_at: '2026-06-29T12:00:00Z',
      updated_at: '2026-06-29T12:00:00Z',
    })
    deleteCollectionMutateAsync.mockClear()
    deleteCollectionMutateAsync.mockResolvedValue(undefined)
    createMetadataTagMutateAsync.mockClear()
    createMetadataTagMutateAsync.mockResolvedValue(kbMetadataTags[0])
    updateMetadataTagMutateAsync.mockClear()
    updateMetadataTagMutateAsync.mockResolvedValue(kbMetadataTags[0])
    archiveMetadataTagMutateAsync.mockClear()
    archiveMetadataTagMutateAsync.mockResolvedValue(undefined)
    unarchiveMetadataTagMutateAsync.mockClear()
    unarchiveMetadataTagMutateAsync.mockResolvedValue(kbMetadataTags[0])
    deleteMetadataTagPermanentlyMutateAsync.mockClear()
    deleteMetadataTagPermanentlyMutateAsync.mockResolvedValue(undefined)
    createAdminChatSessionMutateAsync.mockClear()
    submitAdminChatMessageMutateAsync.mockClear()
    startAdminChatStream.mockClear()
    stopAdminChatStream.mockClear()
    createDashboardInsightRunMutateAsync.mockClear()
    createDashboardInsightRunMutateAsync.mockResolvedValue({
      run_id: 'run-started',
      status: 'pending',
    })
    adminAnalyticsHookCalls.splice(0, adminAnalyticsHookCalls.length)
    adminAnalyticsState.currentInsight = dashboardInsight
    adminAnalyticsState.currentInsightError = false
    adminAnalyticsState.currentInsightLoading = false
    adminAnalyticsState.queries = analyticsQueries
    adminAnalyticsState.queriesError = false
    adminAnalyticsState.queriesLoading = false
    adminAnalyticsState.run = null
    adminAnalyticsState.runError = false
    adminAnalyticsState.runLoading = false
    adminAnalyticsState.summary = analyticsSummary
    adminAnalyticsState.summaryError = false
    adminAnalyticsState.summaryLoading = false
    adminAnalyticsState.createRunError = false
    adminAnalyticsState.createRunPending = false
    adminChatMessages.splice(0, adminChatMessages.length)
    uploadDocumentMutate.mockResolvedValue(kbDocuments[0])
    createAdminChatSessionMutateAsync.mockResolvedValue({
      id: 'admin-chat-session-1',
      title: 'Weekly NIL questions',
      status: 'active',
      context_window_start: null,
      context_window_end: null,
      last_message_at: null,
      created_at: '2026-06-29T12:00:00Z',
      updated_at: '2026-06-29T12:00:00Z',
    })
    submitAdminChatMessageMutateAsync.mockResolvedValue({
      session_id: 'admin-chat-session-1',
      user_message_id: 'admin-user-message-1',
      assistant_message_id: 'admin-assistant-message-1',
      task_id: 'admin-chat-task-1',
      stream_url:
        '/api/v1/admin/chat/sessions/admin-chat-session-1/messages/admin-assistant-message-1/stream?task_id=admin-chat-task-1',
      status: 'streaming',
    })
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
        collection_id: 'collection-compliance',
        tag_slugs: ['nil', 'compliance'],
        visibility_policy: { scope: 'all_athletes' },
        metadata_tags: {
          collection: 'compliance',
          tag_slugs: ['nil', 'compliance'],
          tags: ['NIL', 'Compliance'],
          topics: ['Compliance & NIL', 'NIL', 'Compliance'],
        },
        source_date: '2026-03-01',
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
        collection_id: 'collection-compliance',
        tag_slugs: ['recruiting'],
        visibility_policy: { scope: 'all_athletes' },
        metadata_tags: {
          collection: 'compliance',
          tag_slugs: ['recruiting'],
          tags: ['Recruiting'],
          topics: ['Compliance & NIL', 'Recruiting'],
        },
        source_date: null,
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
        collection_id: 'collection-travel',
        tag_slugs: ['travel', 'old-policy'],
        visibility_policy: { scope: 'all_athletes' },
        metadata_tags: {
          collection: 'travel',
          tag_slugs: ['travel', 'old-policy'],
          tags: ['Travel', 'Old policy'],
          topics: ['Team Travel', 'Travel', 'Old policy'],
        },
        source_date: '2026-06-01',
        kb_service_document_id: 'kb-doc-3',
        created_at: '2026-06-01T12:00:00Z',
        updated_at: '2026-06-01T12:00:00Z',
      },
    ])
    kbCollections.splice(0, kbCollections.length, ...[
      {
        id: 'collection-compliance',
        organization_id: 'org-1',
        slug: 'compliance',
        title: 'Compliance & NIL',
        description: 'NIL, eligibility, and recruiting rules - kept current with department and NCAA policy.',
        icon: 'shield',
        sort_order: 10,
        is_active: true,
        created_at: '2026-06-29T12:00:00Z',
        updated_at: '2026-06-29T12:00:00Z',
      },
      {
        id: 'collection-travel',
        organization_id: 'org-1',
        slug: 'travel',
        title: 'Team Travel',
        description: 'Per-diem rates, charter logistics, and team hotel policy for every sport.',
        icon: 'plane',
        sort_order: 20,
        is_active: true,
        created_at: '2026-06-29T12:00:00Z',
        updated_at: '2026-06-29T12:00:00Z',
      },
      {
        id: 'collection-academics',
        organization_id: 'org-1',
        slug: 'academics',
        title: 'Academic Services',
        description: 'Study-hall rules, tutoring, and academic eligibility support.',
        icon: 'book-open',
        sort_order: 30,
        is_active: true,
        created_at: '2026-06-29T12:00:00Z',
        updated_at: '2026-06-29T12:00:00Z',
      },
      {
        id: 'collection-donor',
        organization_id: 'org-1',
        slug: 'donor',
        title: 'Donor Relations',
        description: 'Giving levels, suite benefits, and booster club answers for boosters.',
        icon: 'users',
        sort_order: 40,
        is_active: true,
        created_at: '2026-06-29T12:00:00Z',
        updated_at: '2026-06-29T12:00:00Z',
      },
    ])
    useUIStore.setState({
      adminTab: 'insights',
      adminChatOpen: false,
      adminTimeWindow: '7d',
    })
  })

  it('denies athlete access', () => {
    currentUser.role = 'athlete'
    renderAdmin()

    expect(screen.getByRole('heading', { name: /admins only/i })).toBeInTheDocument()
    expect(createDashboardInsightRunMutateAsync).not.toHaveBeenCalled()
    expect(adminAnalyticsHookCalls).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ hook: 'summary', enabled: false }),
        expect.objectContaining({ hook: 'queries', enabled: false }),
        expect.objectContaining({ hook: 'current', enabled: false }),
        expect.objectContaining({ hook: 'run', enabled: false }),
      ]),
    )
  })

  it('renders a workspace skeleton while admin auth resolves', () => {
    currentUser.isLoading = true

    renderAdmin()

    expect(screen.getByTestId('admin-workspace-skeleton')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Insights' })).toBeInTheDocument()
    expect(screen.getByText('AI summary')).toBeInTheDocument()
    expect(screen.getByText('Last 7 days')).toBeInTheDocument()
    expect(screen.getByText(/ai generated insights from user queries/i)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /query review/i })).toBeInTheDocument()
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

    const chatWorkspace = screen.getByRole('menuitem', { name: /chat workspace/i })

    expect(chatWorkspace).toBeInTheDocument()
    expect(chatWorkspace).toHaveAttribute('href', '/chat')
    expect(screen.getByRole('menuitem', { name: /privacy policy/i })).toHaveAttribute('href', '/privacy')
    expect(screen.getByRole('menuitem', { name: /terms of service/i })).toHaveAttribute('href', '/terms')
    expect(screen.queryByRole('menuitem', { name: /admin dashboard/i })).not.toBeInTheDocument()
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
    expect(regenerate).toHaveClass('pb-admin-insights-regenerate-control')
    expect(explore).toHaveClass('pb-admin-header-control', 'pb-ui-sm')
    const adminHeaderControlCss = globalsCss.match(/\.pb-admin-header-control\s*{[^}]*}/s)?.[0] ?? ''
    expect(adminHeaderControlCss).toMatch(/align-items:\s*center;/)
    expect(adminHeaderControlCss).toMatch(/box-sizing:\s*border-box;/)
    expect(adminHeaderControlCss).toMatch(/height:\s*36px;/)
    expect(adminHeaderControlCss).toMatch(/padding-inline:\s*10px;/)
    expect(adminHeaderControlCss).toMatch(/width:\s*auto;/)
    expect(adminHeaderControlCss).not.toMatch(/width:\s*152px;/)
    expect(globalsCss).toMatch(
      /\.pb-admin-insights-regenerate-control\s*{[^}]*min-width:\s*132px;/s,
    )
    expect(screen.getByRole('button', { name: /^Insights$/i })).toHaveClass('pb-admin-nav-item')
    expect(screen.getByRole('button', { name: /^Insights$/i })).toHaveClass('pb-focus-control')
    expect(screen.getByRole('button', { name: /Knowledge base 1 failed document/i })).toHaveClass(
      'pb-admin-nav-item',
    )
    expect(screen.getByRole('button', { name: /Users & roles/i })).toHaveClass('pb-admin-nav-item')
    expect(screen.getByText(/AI summary/i)).toBeInTheDocument()
    expect(screen.getByText(/NIL disclosure timing is the clearest support gap/i)).toBeInTheDocument()
    expect(screen.getByText(/NIL questions/i)).toBeInTheDocument()
    expect(screen.getByText(/Nil flags/i)).toBeInTheDocument()
    expect(screen.getByText(/Common topics/i)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /^Risk flags$/i })).toBeInTheDocument()
    expect(screen.getByText(/Common topics/i).closest('section')?.querySelector('.pb-dashboard-breakdown-scroll')).not.toBeNull()
    expect(screen.getByRole('heading', { name: /^Risk flags$/i }).closest('section')?.querySelector('.pb-dashboard-breakdown-scroll')).not.toBeNull()
    expect(screen.getByText(/Query volume/i)).toBeInTheDocument()
    expect(screen.getByText(/128 in window/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Previous query-volume week/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Next query-volume week/i })).not.toBeInTheDocument()
    expect(globalsCss).toMatch(
      /\.pb-dashboard-breakdown-scroll\s*{[^}]*max-height:\s*198px;[^}]*overflow-y:\s*auto;/s,
    )
    expect(globalsCss).toMatch(
      /\.pb-dashboard-breakdown-scroll\s*{[^}]*padding-right:\s*14px;[^}]*scrollbar-gutter:\s*stable;/s,
    )
    expect(screen.getByRole('button', { name: /Knowledge base 1 failed document/i })).toBeInTheDocument()
    expect(screen.queryByText(/Fixture-backed until Phase 4 APIs land/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/Grounded rate/i)).not.toBeInTheDocument()
  })

  it('paginates 30-day query volume by week', async () => {
    currentUser.role = 'super_admin'
    adminAnalyticsState.summary = {
      ...analyticsSummary,
      query_volume: 210,
      volume_series: Array.from({ length: 14 }, (_, index) => ({
        date: `2026-06-${String(index + 1).padStart(2, '0')}`,
        total: index + 1,
        unanswered: index % 3 === 0 ? 1 : 0,
      })),
    }

    renderAdmin()

    await userEvent.click(screen.getByRole('button', { name: /Last 7 days/i }))
    await userEvent.click(screen.getByRole('menuitem', { name: /Last 30 days/i }))

    expect(screen.getByLabelText(/Jun 14: 14 questions/i)).toBeInTheDocument()
    expect(screen.queryByLabelText(/Jun 1: 1 questions/i)).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /Previous query-volume week/i }))

    expect(screen.getByLabelText(/Jun 1: 1 questions/i)).toBeInTheDocument()
    expect(screen.queryByLabelText(/Jun 14: 14 questions/i)).not.toBeInTheDocument()
  })

  it('uses only MVP time windows and sends the selected window to analytics chat', async () => {
    currentUser.role = 'super_admin'
    renderAdmin()

    await userEvent.click(screen.getByRole('button', { name: /Last 7 days/i }))

    expect(screen.getByRole('menuitem', { name: /Last 7 days/i })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /Last 30 days/i })).toBeInTheDocument()
    expect(screen.queryByRole('menuitem', { name: /Custom range/i })).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('menuitem', { name: /Last 30 days/i }))

    await waitFor(() =>
      expect(adminAnalyticsHookCalls).toEqual(
        expect.arrayContaining([
          expect.objectContaining({ hook: 'summary', window: '30d', enabled: true }),
          expect.objectContaining({ hook: 'queries', window: '30d', enabled: true }),
          expect.objectContaining({ hook: 'current', window: '30d', enabled: true }),
        ]),
      ),
    )

    await userEvent.click(screen.getByRole('button', { name: /Explore with AI/i }))
    await userEvent.click(screen.getByRole('button', { name: /What are athletes most confused about this week/i }))

    await waitFor(() =>
      expect(submitAdminChatMessageMutateAsync).toHaveBeenCalledWith({
        sessionId: 'admin-chat-session-1',
        question: 'What are athletes most confused about this week?',
        window: '30d',
      }),
    )
  })

  it('renders anonymized query review rows and expandable details', async () => {
    currentUser.role = 'super_admin'
    renderAdmin()

    const queryReview = screen.getByRole('region', { name: /Query review/i })

    expect(within(queryReview).getByText(/When do I disclose an NIL deal/i)).toBeInTheDocument()
    expect(within(queryReview).getByText(/Can recruiting staff text this prospect/i)).toBeInTheDocument()
    expect(within(queryReview).getByText(/anon_1111/i)).toBeInTheDocument()
    expect(within(queryReview).queryByText(/Jordan Mitchell/i)).not.toBeInTheDocument()
    expect(within(queryReview).queryByText(/j\.mitchell@okstate\.edu/i)).not.toBeInTheDocument()

    await userEvent.click(
      within(queryReview).getByRole('button', {
        name: /Open query details for When do I disclose an NIL deal/i,
      }),
    )

    expect(within(queryReview).getByLabelText(/Message message-1/i)).toBeInTheDocument()
    expect(within(queryReview).getByLabelText(/Answer grounded answer/i)).toBeInTheDocument()
    expect(within(queryReview).getByLabelText(/Response complete/i)).toBeInTheDocument()
  })

  it('passes query-review topic and risk filters into analytics queries', async () => {
    currentUser.role = 'super_admin'
    renderAdmin()

    const queryReview = screen.getByRole('region', { name: /Query review/i })

    await userEvent.click(within(queryReview).getByRole('button', { name: /Filter topic Nil/i }))
    await waitFor(() =>
      expect(adminAnalyticsHookCalls).toContainEqual(
        expect.objectContaining({
          hook: 'queries',
          filters: { topic_labels: ['nil'], risk_labels: [] },
        }),
      ),
    )

    await userEvent.click(within(queryReview).getByRole('button', { name: /Filter risk Recruiting/i }))
    await waitFor(() =>
      expect(adminAnalyticsHookCalls).toContainEqual(
        expect.objectContaining({
          hook: 'queries',
          filters: { topic_labels: ['nil'], risk_labels: ['recruiting'] },
        }),
      ),
    )
  })

  it('paginates query review rows and resets the page when filters change', async () => {
    currentUser.role = 'super_admin'
    adminAnalyticsState.queries = {
      ...analyticsQueries,
      queries: Array.from({ length: 11 }, (_, index) => ({
        message_id: `message-${index + 1}`,
        anonymous_user_key: `anon_${String(index + 1).padStart(4, '0')}`,
        text: `Generated query ${index + 1}`,
        created_at: '2026-06-02T15:32:00Z',
        topic_labels: ['nil'],
        risk_labels: index % 2 === 0 ? ['compliance'] : [],
        response_status: 'complete',
        answer_type: 'grounded_answer',
        unanswered_reason: null,
      })),
    }

    renderAdmin()

    const queryReview = screen.getByRole('region', { name: /Query review/i })
    expect(within(queryReview).getByText(/Generated query 10/i)).toBeInTheDocument()
    expect(within(queryReview).queryByText(/Generated query 11/i)).not.toBeInTheDocument()

    await userEvent.click(within(queryReview).getByRole('button', { name: /Next query page/i }))
    await waitFor(() =>
      expect(adminAnalyticsHookCalls).toContainEqual(
        expect.objectContaining({ hook: 'queries', page: 1 }),
      ),
    )

    await userEvent.click(within(queryReview).getByRole('button', { name: /Filter topic Nil/i }))
    await waitFor(() =>
      expect(adminAnalyticsHookCalls).toContainEqual(
        expect.objectContaining({
          hook: 'queries',
          filters: { topic_labels: ['nil'], risk_labels: [] },
          page: 0,
        }),
      ),
    )
  })

  it('renders a filtered-empty query review state without fake rows', () => {
    currentUser.role = 'super_admin'
    adminAnalyticsState.queries = { ...analyticsQueries, queries: [] }

    renderAdmin()

    const queryReview = screen.getByRole('region', { name: /Query review/i })
    expect(within(queryReview).getByText(/No matching query rows for this window/i)).toBeInTheDocument()
    expect(within(queryReview).queryByText(/When do I disclose an NIL deal/i)).not.toBeInTheDocument()
  })

  it('starts a manual dashboard insight run for concrete UTC windows', async () => {
    currentUser.role = 'super_admin'
    renderAdmin()

    await userEvent.click(screen.getByRole('button', { name: /^Regenerate$/i }))

    await waitFor(() =>
      expect(createDashboardInsightRunMutateAsync).toHaveBeenCalledWith({
        window_start: '2026-06-01T00:00:00.000Z',
        window_end: '2026-06-08T00:00:00.000Z',
        source_filters: {},
      }),
    )
  })

  it('keeps Regenerate disabled without duplicating the AI summary loader while insight generation is active', () => {
    currentUser.role = 'super_admin'
    adminAnalyticsState.createRunPending = true

    renderAdmin()

    const regenerate = screen.getByRole('button', { name: /^Regenerating\.\.\.$/i })

    expect(regenerate).toBeDisabled()
    expect(regenerate).toHaveTextContent(/^Regenerating\.\.\.$/)
    expect(regenerate.querySelector('.pb-spin')).toBeInTheDocument()
    expect(screen.queryByText(/^Generating\.\.\.$/i)).not.toBeInTheDocument()
    expect(screen.getByText(/NIL disclosure timing is the clearest support gap/i)).toBeInTheDocument()
  })

  it('renders an empty-current dashboard insight state', () => {
    currentUser.role = 'super_admin'
    adminAnalyticsState.currentInsight = null

    renderAdmin()

    expect(
      screen.getByText(/No dashboard insight has been generated for this window yet/i),
    ).toBeInTheDocument()
  })

  it('renders failed dashboard insight run visibility', () => {
    currentUser.role = 'super_admin'
    adminAnalyticsState.currentInsight = null
    adminAnalyticsState.run = {
      id: 'run-failed',
      organization_id: 'org-1',
      requested_by: 'u1',
      trigger_type: 'manual',
      status: 'failed',
      window_start: '2026-06-01T00:00:00Z',
      window_end: '2026-06-08T00:00:00Z',
      source_filters: {},
      error_message: 'RuntimeError',
      created_at: '2026-06-08T12:00:00Z',
      updated_at: '2026-06-08T12:01:00Z',
      output: null,
    }

    renderAdmin()

    expect(screen.getByText(/^Failed$/i)).toBeInTheDocument()
    expect(screen.getByText('RuntimeError')).toBeInTheDocument()
    expect(screen.queryByText(/secret/i)).not.toBeInTheDocument()
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
    expect(screen.getByRole('button', { name: /Manage tags/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /New collection/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Compliance & NIL collection/i })).toHaveTextContent('2 documents')
    expect(screen.getByRole('button', { name: /Compliance & NIL collection/i })).toHaveTextContent('1 needs attention')
    expect(screen.getByRole('button', { name: /Team Travel collection/i })).toHaveTextContent('1 document')
    expect(screen.getByRole('button', { name: /Team Travel collection/i })).toHaveTextContent('All ready')
    expect(screen.getByRole('button', { name: /Academic Services collection/i })).toHaveTextContent('No documents yet')
    expect(screen.getByRole('button', { name: /Donor Relations collection/i })).toHaveTextContent('No documents yet')
  })

  it('lets super admins create KB collections with title, description, and icon', async () => {
    const user = userEvent.setup({ delay: null })
    currentUser.role = 'super_admin'
    useUIStore.setState({ adminTab: 'kb' })
    renderAdmin()

    await user.click(screen.getByRole('button', { name: /New collection/i }))

    const dialog = screen.getByRole('dialog', { name: /New collection/i })
    const iconOptions = Array.from(dialog.querySelectorAll('.pb-admin-kb-icon-option'))
    const shieldOption = within(dialog).getByRole('button', { name: /^Shield$/i, pressed: true })
    const bookOption = within(dialog).getByRole('button', { name: /^Book$/i, pressed: false })

    expect(shieldOption).toHaveClass('is-selected')
    expect(iconOptions).toHaveLength(5)
    for (const option of iconOptions) {
      expect(option.querySelectorAll('svg')).toHaveLength(1)
    }

    fireEvent.change(within(dialog).getByLabelText(/Title/i), { target: { value: 'Sport rules' } })
    fireEvent.change(within(dialog).getByLabelText(/Description/i), {
      target: { value: 'Sport-specific rules and team policies.' },
    })
    await user.click(bookOption)

    expect(within(dialog).getByRole('button', { name: /^Book$/i, pressed: true })).toHaveClass('is-selected')
    expect(within(dialog).getByRole('button', { name: /^Shield$/i, pressed: false })).not.toHaveClass(
      'is-selected',
    )
    for (const option of iconOptions) {
      expect(option.querySelectorAll('svg')).toHaveLength(1)
    }

    await user.click(within(dialog).getByRole('button', { name: /Create collection/i }))

    expect(createCollectionMutateAsync).toHaveBeenCalledWith({
      title: 'Sport rules',
      description: 'Sport-specific rules and team policies.',
      icon: 'book-open',
    })
  })

  it('greys out collection delete when documents still exist and explains why', async () => {
    currentUser.role = 'super_admin'
    useUIStore.setState({ adminTab: 'kb' })
    renderAdmin()

    await userEvent.click(screen.getByRole('button', { name: /Collection actions for Compliance & NIL/i }))

    const deleteAction = screen.getByRole('menuitem', { name: /Delete collection/i })
    expect(deleteAction).toHaveAttribute('aria-disabled', 'true')

    await userEvent.hover(deleteAction)

    expect(await screen.findAllByText(/Delete the documents in this collection first/i)).not.toHaveLength(0)

    await userEvent.click(deleteAction)

    expect(deleteCollectionMutateAsync).not.toHaveBeenCalled()
  })

  it('lets super admins delete empty KB collections after confirmation', async () => {
    currentUser.role = 'super_admin'
    useUIStore.setState({ adminTab: 'kb' })
    renderAdmin()

    await userEvent.click(screen.getByRole('button', { name: /Collection actions for Academic Services/i }))
    await userEvent.click(screen.getByRole('menuitem', { name: /Delete collection/i }))

    const dialog = screen.getByRole('dialog', { name: /Delete collection/i })
    expect(within(dialog).getByText(/removes the empty collection/i)).toHaveTextContent(
      'Delete Academic Services?',
    )

    await userEvent.click(within(dialog).getByRole('button', { name: /Delete collection/i }))

    expect(deleteCollectionMutateAsync).toHaveBeenCalledWith('collection-academics')
  })

  it('lets super admins manage active and archived metadata tag presets', async () => {
    currentUser.role = 'super_admin'
    useUIStore.setState({ adminTab: 'kb' })
    renderAdmin()

    await userEvent.click(screen.getByRole('button', { name: /Manage tags/i }))

    const dialog = screen.getByRole('dialog', { name: /Manage tags/i })
    expect(within(dialog).getByRole('heading', { name: /Active tags/i })).toBeInTheDocument()
    expect(within(dialog).getByRole('heading', { name: /Archived tags/i })).toBeInTheDocument()
    expect(within(dialog).queryByLabelText(/Search tags/i)).not.toBeInTheDocument()
    expect(within(dialog).queryByText(/^nil$/)).not.toBeInTheDocument()
    expect(within(dialog).queryByText(/^legacy$/)).not.toBeInTheDocument()

    await userEvent.type(within(dialog).getByLabelText(/New metadata tag label/i), 'Sport rules')
    await userEvent.click(within(dialog).getByRole('button', { name: /^Add$/i }))

    expect(createMetadataTagMutateAsync).toHaveBeenCalledWith({ label: 'Sport rules' })

    await userEvent.click(within(dialog).getByRole('button', { name: /Rename NIL/i }))
    await userEvent.clear(within(dialog).getByLabelText(/Edit NIL/i))
    await userEvent.type(within(dialog).getByLabelText(/Edit NIL/i), 'NIL policy')
    await userEvent.click(within(dialog).getByRole('button', { name: /Save NIL/i }))

    expect(updateMetadataTagMutateAsync).toHaveBeenCalledWith({
      tagId: 'tag-nil',
      request: { label: 'NIL policy' },
    })

    await userEvent.click(within(dialog).getByRole('button', { name: /Archive Compliance/i }))

    expect(archiveMetadataTagMutateAsync).toHaveBeenCalledWith('tag-compliance')

    await userEvent.click(within(dialog).getByRole('button', { name: /Unarchive Legacy/i }))
    expect(unarchiveMetadataTagMutateAsync).toHaveBeenCalledWith('tag-archived')

    await userEvent.click(within(dialog).getByRole('button', { name: /Delete Legacy permanently/i }))
    expect(deleteMetadataTagPermanentlyMutateAsync).toHaveBeenCalledWith('tag-archived')

    expect(
      within(dialog).getByRole('button', { name: /Delete Old policy permanently/i }),
    ).toBeDisabled()
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

  it('does not show a knowledge-base refresh state during metadata tag refetches', () => {
    currentUser.role = 'super_admin'
    adminQueryState.kbMetadataFetching = true
    useUIStore.setState({ adminTab: 'kb' })

    renderAdmin()

    expect(screen.getByRole('button', { name: /Compliance & NIL collection/i })).toBeInTheDocument()
    expect(screen.queryByText(/refreshing knowledge base/i)).not.toBeInTheDocument()
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
      collection_id: 'collection-travel',
      tag_slugs: ['travel'],
      visibility_policy: { scope: 'all_athletes' },
      metadata_tags: {
        collection: 'travel',
        tag_slugs: ['travel'],
        tags: ['Travel'],
        topics: ['Team Travel', 'Travel'],
      },
      source_date: null,
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

  it('uploads a KB document with dialog metadata, local progress, and queued status', async () => {
    const user = userEvent.setup({ delay: null })
    currentUser.role = 'super_admin'
    useUIStore.setState({ adminTab: 'kb' })
    uploadDocumentMutate.mockImplementation(async (request) => {
      request.onProgress?.({ loaded: 5, percent: 50, total: 10 })
      return { ...kbDocuments[0], id: 'doc-uploaded', title: request.file.name }
    })
    renderAdmin()

    await user.click(screen.getByRole('button', { name: /Compliance & NIL collection/i }))
    await user.upload(
      getKnowledgeBaseUploadInput(),
      new File(['hello'], 'athlete-handbook.pdf', { type: 'application/pdf' }),
    )
    const dialog = screen.getByRole('dialog', { name: /Upload document/i })
    fireEvent.change(within(dialog).getByLabelText(/Title/i), { target: { value: 'Athlete handbook' } })
    await user.click(within(dialog).getByRole('button', { name: /Add NIL/i }))
    await user.click(within(dialog).getByRole('button', { name: /Add Compliance/i }))
    fireEvent.change(within(dialog).getByLabelText(/Source date/i), { target: { value: '2026-06-29' } })
    await user.click(within(dialog).getByRole('button', { name: /^Upload$/i }))

    expect(uploadDocumentMutate).toHaveBeenCalledWith(
      expect.objectContaining({
        collection_id: 'collection-compliance',
        file: expect.objectContaining({ name: 'athlete-handbook.pdf' }),
        onProgress: expect.any(Function),
        source_date: '2026-06-29',
        tag_slugs: ['nil', 'compliance'],
        title: 'Athlete handbook',
      }),
    )
    expect(await screen.findByText('athlete-handbook.pdf')).toBeInTheDocument()
    expect(await screen.findByText('Queued')).toBeInTheDocument()
  })

  it('blocks invalid upload dialog dates before creating an intent', async () => {
    currentUser.role = 'admin'
    useUIStore.setState({ adminTab: 'kb' })
    renderAdmin()

    await userEvent.click(screen.getByRole('button', { name: /Compliance & NIL collection/i }))
    await userEvent.upload(
      getKnowledgeBaseUploadInput(),
      new File(['hello'], 'bad-date.pdf', { type: 'application/pdf' }),
    )
    const dialog = screen.getByRole('dialog', { name: /Upload document/i })
    await userEvent.type(within(dialog).getByLabelText(/Source date/i), 'June 29, 2026')
    await userEvent.click(within(dialog).getByRole('button', { name: /^Upload$/i }))

    expect(within(dialog).getByText(/Use YYYY-MM-DD/i)).toBeInTheDocument()
    expect(uploadDocumentMutate).not.toHaveBeenCalled()
  })

  it('shows a safe admin upload failure and retries with the same metadata', async () => {
    currentUser.role = 'super_admin'
    useUIStore.setState({ adminTab: 'kb' })
    uploadDocumentMutate.mockRejectedValueOnce(new Error('File upload failed before Playbook received it.'))
    uploadDocumentMutate.mockResolvedValueOnce(kbDocuments[0])
    renderAdmin()

    await userEvent.click(screen.getByRole('button', { name: /Compliance & NIL collection/i }))
    await userEvent.upload(
      getKnowledgeBaseUploadInput(),
      new File(['hello'], 'retry-me.pdf', { type: 'application/pdf' }),
    )
    const dialog = screen.getByRole('dialog', { name: /Upload document/i })
    await userEvent.click(within(dialog).getByRole('button', { name: /Add Compliance/i }))
    await userEvent.type(within(dialog).getByLabelText(/Source date/i), '2026-06-28')
    await userEvent.click(within(dialog).getByRole('button', { name: /^Upload$/i }))

    expect(await screen.findByText('File upload failed before Playbook received it.')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /try again/i }))

    expect(uploadDocumentMutate).toHaveBeenCalledTimes(2)
    expect(uploadDocumentMutate).toHaveBeenLastCalledWith(
      expect.objectContaining({
        collection_id: 'collection-compliance',
        source_date: '2026-06-28',
        tag_slugs: ['compliance'],
        title: 'retry-me.pdf',
      }),
    )
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

  it('lets department admins manage KB documents but not users or local collections', async () => {
    currentUser.role = 'admin'
    useUIStore.setState({ adminTab: 'kb' })
    renderAdmin()

    expect(screen.queryByRole('button', { name: /users & roles/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /New collection/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Manage tags/i })).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /Compliance & NIL collection/i }))

    expect(screen.getByRole('button', { name: /Upload knowledge-base document to Compliance & NIL/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Retry RECRUITING_DEAD_PERIODS.PDF/i })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /Actions for RECRUITING_DEAD_PERIODS.PDF/i }))

    expect(screen.getByRole('menuitem', { name: /Delete \/ archive/i })).toBeInTheDocument()
  })

  it('opens collection detail and routes document actions through KB mutations', async () => {
    currentUser.role = 'super_admin'
    useUIStore.setState({ adminTab: 'kb' })
    renderAdmin()

    await userEvent.click(screen.getByRole('button', { name: /Compliance & NIL collection/i }))

    expect(screen.getByRole('heading', { name: 'Compliance & NIL' })).toBeInTheDocument()
    expect(screen.getByText(/^2 documents$/i)).toBeInTheDocument()
    expect(screen.getByText('NIL_POLICY_2025.PDF')).toBeInTheDocument()
    expect(screen.getByText('RECRUITING_DEAD_PERIODS.PDF')).toBeInTheDocument()
    expect(screen.getByText(/Scanned PDF - no extractable text layer/i)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /Retry RECRUITING_DEAD_PERIODS.PDF/i }))
    expect(retryDocumentMutate).toHaveBeenCalledWith('doc-recruiting')

    await userEvent.click(screen.getByRole('button', { name: /Actions for RECRUITING_DEAD_PERIODS.PDF/i }))
    await userEvent.click(screen.getByRole('menuitem', { name: /Delete \/ archive/i }))
    expect(deleteDocumentMutate).toHaveBeenCalledWith('doc-recruiting')

    await userEvent.click(screen.getByRole('button', { name: /All collections/i }))
    expect(screen.getByRole('heading', { name: 'Knowledge base' })).toBeInTheDocument()
  })

  it('saves preset tag slugs and clears source date when saving metadata', async () => {
    currentUser.role = 'admin'
    useUIStore.setState({ adminTab: 'kb' })
    renderAdmin()

    await userEvent.click(screen.getByRole('button', { name: /Compliance & NIL collection/i }))
    await userEvent.click(screen.getByRole('button', { name: /Actions for NIL_POLICY_2025.PDF/i }))
    await userEvent.click(screen.getByRole('menuitem', { name: /Edit metadata/i }))

    const dialog = screen.getByRole('dialog', { name: /Edit metadata/i })
    await userEvent.clear(within(dialog).getByLabelText(/Source date/i))
    await userEvent.click(within(dialog).getByRole('button', { name: /Save changes/i }))

    expect(updateDocumentMutateAsync).toHaveBeenCalledWith({
      documentId: 'doc-nil-policy',
      metadata: {
        source_date: null,
        tag_slugs: ['nil', 'compliance'],
      },
    })
    await waitFor(() =>
      expect(screen.queryByRole('dialog', { name: /Edit metadata/i })).not.toBeInTheDocument(),
    )
  })

  it('keeps the metadata drawer open when save fails', async () => {
    currentUser.role = 'admin'
    updateDocumentMutateAsync.mockRejectedValueOnce(new Error('Metadata update failed.'))
    useUIStore.setState({ adminTab: 'kb' })
    renderAdmin()

    await userEvent.click(screen.getByRole('button', { name: /Compliance & NIL collection/i }))
    await userEvent.click(screen.getByRole('button', { name: /Actions for NIL_POLICY_2025.PDF/i }))
    await userEvent.click(screen.getByRole('menuitem', { name: /Edit metadata/i }))
    await userEvent.click(screen.getByRole('button', { name: /Save changes/i }))

    expect(await screen.findByText('Metadata update failed.')).toBeInTheDocument()
    expect(screen.getByRole('dialog', { name: /Edit metadata/i })).toBeInTheDocument()
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

    expect(screen.getByRole('heading', { name: 'Users & roles' })).toHaveClass('pb-page-title')
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

    const panel = screen.getByRole('complementary', { name: /Analytics AI Agent/i })
    const panelHeader = within(panel).getByRole('heading', { name: /Analytics AI Agent/i }).closest('header')

    expect(panel).toBeInTheDocument()
    expect(panelHeader).toHaveClass('pb-panel-header')
    expect(panelHeader).not.toHaveClass('pb-admin-chat-panel-header')
    expect(globalsCss).not.toMatch(/\.pb-admin-chat-panel-header\s*{/)

    await userEvent.click(screen.getByRole('button', { name: /What are athletes most confused about this week/i }))

    await waitFor(() =>
      expect(createAdminChatSessionMutateAsync).toHaveBeenCalledWith({
        title: 'What are athletes most confused about this week?',
      }),
    )
    expect(submitAdminChatMessageMutateAsync).toHaveBeenCalledWith({
      sessionId: 'admin-chat-session-1',
      question: 'What are athletes most confused about this week?',
      window: '7d',
    })
    expect(startAdminChatStream).toHaveBeenCalledWith({
      assistantMessageId: 'admin-assistant-message-1',
      sessionId: 'admin-chat-session-1',
      streamUrl:
        '/api/v1/admin/chat/sessions/admin-chat-session-1/messages/admin-assistant-message-1/stream?task_id=admin-chat-task-1',
    })
  })

  it('greys out Explore with AI while the analytics chat side panel is open', async () => {
    currentUser.role = 'super_admin'
    renderAdmin()

    const explore = screen.getByRole('button', { name: /Explore with AI/i })

    expect(explore).toBeEnabled()

    await userEvent.click(explore)

    expect(screen.getByRole('complementary', { name: /Analytics AI Agent/i })).toBeInTheDocument()
    expect(explore).toBeDisabled()

    await userEvent.click(screen.getByRole('button', { name: /Close analytics chat/i }))

    expect(screen.queryByRole('complementary', { name: /Analytics AI Agent/i })).not.toBeInTheDocument()
    expect(explore).toBeEnabled()
  })

  it('renders the pending admin chat turn immediately after send', async () => {
    currentUser.role = 'super_admin'
    createAdminChatSessionMutateAsync.mockImplementation(() => new Promise(() => {}))
    renderAdmin()

    await userEvent.click(screen.getByRole('button', { name: /Explore with AI/i }))
    await userEvent.click(screen.getByRole('button', { name: /What are athletes most confused about this week/i }))

    expect(screen.getByText('What are athletes most confused about this week?')).toBeInTheDocument()
    expect(screen.getAllByText('Thinking...')).toHaveLength(1)
    expect(screen.getByText('Thinking...')).toHaveClass('pb-thinking-shimmer')
  })
}, 15_000)
