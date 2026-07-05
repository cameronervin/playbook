import { describe, expect, it } from 'vitest'
import {
  normalizeAdminAnalyticsQueryFilters,
  queryReviewPaginationParams,
  stableAdminAnalyticsQueryFilters,
  isActiveDashboardInsightStatus,
  toManualRunWindow,
  toReadWindowParams,
} from '@/src/hooks/useAdminAnalytics'

describe('admin analytics hooks helpers', () => {
  it('uses shorthand windows for reads and concrete timestamps for manual runs', () => {
    const now = new Date('2026-06-08T12:30:00.000Z')

    expect(toReadWindowParams('7d')).toEqual({ window: '7d' })
    expect(toManualRunWindow('7d', now)).toEqual({
      window_start: '2026-06-01T12:30:00.000Z',
      window_end: '2026-06-08T12:30:00.000Z',
      source_filters: {},
    })
    expect(toManualRunWindow('30d', now).window_start).toBe(
      '2026-05-09T12:30:00.000Z',
    )
    expect(toReadWindowParams('30d')).toEqual({ window: '30d' })
  })

  it('polls only active dashboard insight statuses', () => {
    expect(isActiveDashboardInsightStatus('pending')).toBe(true)
    expect(isActiveDashboardInsightStatus('processing')).toBe(true)
    expect(isActiveDashboardInsightStatus('completed')).toBe(false)
    expect(isActiveDashboardInsightStatus('failed')).toBe(false)
  })

  it('normalizes query-review filters for URLs and stable query keys', () => {
    const filters = normalizeAdminAnalyticsQueryFilters({
      topic_labels: [' nil ', 'compliance', 'nil', ''],
      risk_labels: ['recruiting', ' compliance ', 'recruiting'],
    })

    expect(filters).toEqual({
      topic_labels: ['nil', 'compliance'],
      risk_labels: ['recruiting', 'compliance'],
    })
    expect(stableAdminAnalyticsQueryFilters(filters)).toEqual({
      topic_labels: ['compliance', 'nil'],
      risk_labels: ['compliance', 'recruiting'],
    })
  })

  it('builds query-review sentinel pagination params', () => {
    expect(queryReviewPaginationParams(0)).toEqual({ limit: 11, offset: 0 })
    expect(queryReviewPaginationParams(1)).toEqual({ limit: 11, offset: 10 })
  })
})
