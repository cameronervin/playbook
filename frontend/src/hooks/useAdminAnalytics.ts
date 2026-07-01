import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createDashboardInsightRun,
  getAdminAnalyticsSummary,
  getCurrentDashboardInsight,
  getDashboardInsightRun,
  listAdminAnalyticsQueries,
  listDashboardInsightOutputs,
} from '@/src/lib/api/endpoints/adminAnalytics'
import { QUERY_KEYS } from '@/src/lib/constants/config'
import type {
  AdminAnalyticsQueryFilters,
  AdminAnalyticsWindowParams,
  AdminTimeWindow,
  DashboardInsightRunCreateRequest,
  DashboardInsightRunStatus,
} from '@/src/types/adminAnalytics'

const DASHBOARD_INSIGHT_RUN_REFETCH_MS = 3_000
export const QUERY_REVIEW_PAGE_SIZE = 10
const QUERY_REVIEW_FETCH_LIMIT = QUERY_REVIEW_PAGE_SIZE + 1
const EMPTY_QUERY_FILTERS: Required<AdminAnalyticsQueryFilters> = {
  topic_labels: [],
  risk_labels: [],
}

export const useAdminAnalyticsSummary = (
  timeWindow: AdminTimeWindow,
  enabled: boolean,
) =>
  useQuery({
    queryKey: [QUERY_KEYS.adminAnalyticsSummary, timeWindow],
    queryFn: () => getAdminAnalyticsSummary(toReadWindowParams(timeWindow)),
    enabled,
  })

export const useAdminAnalyticsQueries = (
  timeWindow: AdminTimeWindow,
  enabled: boolean,
  filters: AdminAnalyticsQueryFilters = EMPTY_QUERY_FILTERS,
  page = 0,
) =>
  useQuery({
    queryKey: [
      QUERY_KEYS.adminAnalyticsQueries,
      timeWindow,
      stableAdminAnalyticsQueryFilters(filters),
      page,
    ],
    queryFn: () =>
      listAdminAnalyticsQueries({
        ...toReadWindowParams(timeWindow),
        ...normalizeAdminAnalyticsQueryFilters(filters),
        ...queryReviewPaginationParams(page),
      }),
    enabled,
    placeholderData: keepPreviousData,
  })

export const useCurrentDashboardInsight = (
  timeWindow: AdminTimeWindow,
  enabled: boolean,
) =>
  useQuery({
    queryKey: [QUERY_KEYS.dashboardInsightCurrent, timeWindow],
    queryFn: () => getCurrentDashboardInsight(toReadWindowParams(timeWindow)),
    enabled,
  })

export const useDashboardInsightOutputs = (enabled: boolean) =>
  useQuery({
    queryKey: [QUERY_KEYS.dashboardInsightOutputs],
    queryFn: listDashboardInsightOutputs,
    enabled,
  })

export const useDashboardInsightRun = (
  runId: string | null,
  enabled: boolean,
) =>
  useQuery({
    queryKey: [QUERY_KEYS.dashboardInsightRun, runId],
    queryFn: () => getDashboardInsightRun(runId ?? ''),
    enabled: enabled && Boolean(runId),
    refetchInterval: (query) =>
      isActiveDashboardInsightStatus(query.state.data?.status)
        ? DASHBOARD_INSIGHT_RUN_REFETCH_MS
        : false,
  })

export const useCreateDashboardInsightRun = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (request: DashboardInsightRunCreateRequest) =>
      createDashboardInsightRun(request),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: [QUERY_KEYS.dashboardInsightOutputs],
        }),
        queryClient.invalidateQueries({
          queryKey: [QUERY_KEYS.dashboardInsightCurrent],
        }),
      ])
    },
  })
}

export function toReadWindowParams(
  timeWindow: AdminTimeWindow,
): AdminAnalyticsWindowParams {
  return { window: timeWindow }
}

export function normalizeAdminAnalyticsQueryFilters(
  filters: AdminAnalyticsQueryFilters = EMPTY_QUERY_FILTERS,
): Required<AdminAnalyticsQueryFilters> {
  return {
    topic_labels: normalizeFilterValues(filters.topic_labels),
    risk_labels: normalizeFilterValues(filters.risk_labels),
  }
}

export function stableAdminAnalyticsQueryFilters(
  filters: AdminAnalyticsQueryFilters = EMPTY_QUERY_FILTERS,
): Required<AdminAnalyticsQueryFilters> {
  const normalized = normalizeAdminAnalyticsQueryFilters(filters)
  return {
    topic_labels: [...normalized.topic_labels].sort(),
    risk_labels: [...normalized.risk_labels].sort(),
  }
}

export function queryReviewPaginationParams(
  page: number,
): { limit: number; offset: number } {
  return {
    limit: QUERY_REVIEW_FETCH_LIMIT,
    offset: Math.max(0, page) * QUERY_REVIEW_PAGE_SIZE,
  }
}

export function toManualRunWindow(
  timeWindow: AdminTimeWindow,
  now: Date = new Date(),
): DashboardInsightRunCreateRequest {
  const days = timeWindow === '30d' ? 30 : 7
  const windowEnd = new Date(now)
  const windowStart = new Date(windowEnd)
  windowStart.setUTCDate(windowStart.getUTCDate() - days)
  return {
    window_start: windowStart.toISOString(),
    window_end: windowEnd.toISOString(),
    source_filters: {},
  }
}

export function isActiveDashboardInsightStatus(
  status: DashboardInsightRunStatus | undefined,
): boolean {
  return status === 'pending' || status === 'processing'
}

function normalizeFilterValues(values: string[] | undefined): string[] {
  const normalized: string[] = []
  const seen = new Set<string>()
  values?.forEach((value) => {
    const label = value.trim()
    if (!label || seen.has(label)) return
    normalized.push(label)
    seen.add(label)
  })
  return normalized
}
