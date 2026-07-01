import { describe, expect, it } from 'vitest'
import {
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
    expect(toManualRunWindow('30d', now)?.window_start).toBe(
      '2026-05-09T12:30:00.000Z',
    )
  })

  it('keeps custom ranges inert until a date-range picker exists', () => {
    expect(toReadWindowParams('custom')).toEqual({})
    expect(toManualRunWindow('custom', new Date('2026-06-08T12:30:00.000Z'))).toBeNull()
  })

  it('polls only active dashboard insight statuses', () => {
    expect(isActiveDashboardInsightStatus('pending')).toBe(true)
    expect(isActiveDashboardInsightStatus('processing')).toBe(true)
    expect(isActiveDashboardInsightStatus('completed')).toBe(false)
    expect(isActiveDashboardInsightStatus('failed')).toBe(false)
  })
})
