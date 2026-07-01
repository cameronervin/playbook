import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
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
  AdminAnalyticsWindowParams,
  AdminTimeWindow,
  DashboardInsightRunCreateRequest,
  DashboardInsightRunStatus,
} from '@/src/types/adminAnalytics'

const DASHBOARD_INSIGHT_RUN_REFETCH_MS = 3_000
const QUERY_REVIEW_LIMIT = 500

export const useAdminAnalyticsSummary = (
  timeWindow: AdminTimeWindow,
  enabled: boolean,
) =>
  useQuery({
    queryKey: [QUERY_KEYS.adminAnalyticsSummary, timeWindow],
    queryFn: () => getAdminAnalyticsSummary(toReadWindowParams(timeWindow)),
    enabled: enabled && timeWindow !== 'custom',
  })

export const useAdminAnalyticsQueries = (
  timeWindow: AdminTimeWindow,
  enabled: boolean,
) =>
  useQuery({
    queryKey: [QUERY_KEYS.adminAnalyticsQueries, timeWindow],
    queryFn: () =>
      listAdminAnalyticsQueries({
        ...toReadWindowParams(timeWindow),
        limit: QUERY_REVIEW_LIMIT,
      }),
    enabled: enabled && timeWindow !== 'custom',
  })

export const useCurrentDashboardInsight = (
  timeWindow: AdminTimeWindow,
  enabled: boolean,
) =>
  useQuery({
    queryKey: [QUERY_KEYS.dashboardInsightCurrent, timeWindow],
    queryFn: () => getCurrentDashboardInsight(toReadWindowParams(timeWindow)),
    enabled: enabled && timeWindow !== 'custom',
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
  if (timeWindow === 'custom') return {}
  return { window: timeWindow }
}

export function toManualRunWindow(
  timeWindow: AdminTimeWindow,
  now: Date = new Date(),
): DashboardInsightRunCreateRequest | null {
  if (timeWindow === 'custom') return null
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
