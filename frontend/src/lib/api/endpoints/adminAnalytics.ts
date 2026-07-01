import { ApiError, apiClient } from '@/src/lib/api/client'
import { API_VERSION } from '@/src/lib/constants/config'
import type {
  AdminAnalyticsQueryList,
  AdminAnalyticsQueryFilters,
  AdminAnalyticsSummary,
  AdminAnalyticsWindowParams,
  DashboardInsight,
  DashboardInsightRun,
  DashboardInsightRunCreateRequest,
  DashboardInsightRunStart,
} from '@/src/types/adminAnalytics'

const ADMIN_PATH = `/api/${API_VERSION}/admin`
const ANALYTICS_PATH = `${ADMIN_PATH}/analytics`
const DASHBOARD_INSIGHTS_PATH = `${ADMIN_PATH}/dashboard-insights`

interface QueryListParams extends AdminAnalyticsWindowParams, AdminAnalyticsQueryFilters {
  limit?: number
  offset?: number
}

export const getAdminAnalyticsSummary = (
  params: AdminAnalyticsWindowParams = {},
): Promise<AdminAnalyticsSummary> =>
  apiClient<AdminAnalyticsSummary>(
    `${ANALYTICS_PATH}/summary${toQueryString(params)}`,
  )

export const listAdminAnalyticsQueries = (
  params: QueryListParams = {},
): Promise<AdminAnalyticsQueryList> =>
  apiClient<AdminAnalyticsQueryList>(
    `${ANALYTICS_PATH}/queries${toQueryString(params)}`,
  )

export const getCurrentDashboardInsight = async (
  params: AdminAnalyticsWindowParams = {},
): Promise<DashboardInsight | null> => {
  try {
    return await apiClient<DashboardInsight>(
      `${DASHBOARD_INSIGHTS_PATH}/current${toQueryString(params)}`,
    )
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null
    throw error
  }
}

export const listDashboardInsightOutputs = (): Promise<DashboardInsight[]> =>
  apiClient<DashboardInsight[]>(`${DASHBOARD_INSIGHTS_PATH}/outputs`)

export const getDashboardInsightRun = (
  runId: string,
): Promise<DashboardInsightRun> =>
  apiClient<DashboardInsightRun>(`${DASHBOARD_INSIGHTS_PATH}/runs/${runId}`)

export const createDashboardInsightRun = (
  request: DashboardInsightRunCreateRequest,
): Promise<DashboardInsightRunStart> =>
  apiClient<DashboardInsightRunStart>(`${DASHBOARD_INSIGHTS_PATH}/runs`, {
    method: 'POST',
    json: {
      window_start: request.window_start,
      window_end: request.window_end,
      source_filters: request.source_filters ?? {},
    },
  })

function toQueryString(params: AdminAnalyticsWindowParams | QueryListParams): string {
  const searchParams = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined) return
    if (Array.isArray(value)) {
      value.forEach((item) => searchParams.append(key, item))
      return
    }
    searchParams.set(key, String(value))
  })
  const serialized = searchParams.toString()
  return serialized ? `?${serialized}` : ''
}
