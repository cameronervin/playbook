import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, apiClient } from '@/src/lib/api/client'
import {
  createDashboardInsightRun,
  getCurrentDashboardInsight,
  getDashboardInsightRun,
  listAdminAnalyticsQueries,
  getAdminAnalyticsSummary,
} from '@/src/lib/api/endpoints/adminAnalytics'

vi.mock('@/src/lib/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/src/lib/api/client')>()
  return {
    ...actual,
    apiClient: vi.fn(),
  }
})

describe('admin analytics endpoints', () => {
  beforeEach(() => {
    vi.mocked(apiClient).mockReset()
  })

  it('fetches analytics summary and query rows for a shorthand window', async () => {
    vi.mocked(apiClient)
      .mockResolvedValueOnce({ query_volume: 3 })
      .mockResolvedValueOnce({ queries: [] })
      .mockResolvedValueOnce({ queries: [] })

    await getAdminAnalyticsSummary({ window: '7d' })
    await listAdminAnalyticsQueries({ window: '7d', limit: 11, offset: 10 })
    await listAdminAnalyticsQueries({
      window: '7d',
      topic_labels: ['nil', 'compliance'],
      risk_labels: ['recruiting'],
    })

    expect(apiClient).toHaveBeenNthCalledWith(
      1,
      '/api/v1/admin/analytics/summary?window=7d',
    )
    expect(apiClient).toHaveBeenNthCalledWith(
      2,
      '/api/v1/admin/analytics/queries?window=7d&limit=11&offset=10',
    )
    expect(apiClient).toHaveBeenNthCalledWith(
      3,
      '/api/v1/admin/analytics/queries?window=7d&topic_labels=nil&topic_labels=compliance&risk_labels=recruiting',
    )
  })

  it('normalizes a missing current dashboard insight to null', async () => {
    vi.mocked(apiClient).mockRejectedValueOnce(
      new ApiError('Dashboard insight output not found: current', 404, {
        code: 'NOT_FOUND',
      }),
    )

    await expect(getCurrentDashboardInsight({ window: '7d' })).resolves.toBeNull()

    expect(apiClient).toHaveBeenCalledWith(
      '/api/v1/admin/dashboard-insights/current?window=7d',
    )
  })

  it('creates and polls dashboard insight runs', async () => {
    vi.mocked(apiClient)
      .mockResolvedValueOnce({ run_id: 'run-1', status: 'pending' })
      .mockResolvedValueOnce({ id: 'run-1', status: 'completed', output: null })

    await createDashboardInsightRun({
      window_start: '2026-06-01T00:00:00.000Z',
      window_end: '2026-06-08T00:00:00.000Z',
      source_filters: {},
    })
    await getDashboardInsightRun('run-1')

    expect(apiClient).toHaveBeenNthCalledWith(1, '/api/v1/admin/dashboard-insights/runs', {
      method: 'POST',
      json: {
        window_start: '2026-06-01T00:00:00.000Z',
        window_end: '2026-06-08T00:00:00.000Z',
        source_filters: {},
      },
    })
    expect(apiClient).toHaveBeenNthCalledWith(
      2,
      '/api/v1/admin/dashboard-insights/runs/run-1',
    )
  })
})
