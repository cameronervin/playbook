import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useSessionActivity } from '@/src/hooks/useSessionActivity'
import { refreshSession } from '@/src/lib/api/endpoints/auth'

vi.mock('@/src/lib/api/endpoints/auth', () => ({
  refreshSession: vi.fn(async () => undefined),
}))

describe('useSessionActivity', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.mocked(refreshSession).mockClear()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('refreshes on visible user activity and throttles repeated activity', () => {
    renderHook(() => useSessionActivity({ enabled: true, throttleMs: 300_000 }))

    window.dispatchEvent(new Event('pointerdown'))
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'a' }))

    expect(refreshSession).toHaveBeenCalledOnce()

    vi.advanceTimersByTime(300_000)
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'b' }))

    expect(refreshSession).toHaveBeenCalledTimes(2)
  })

  it('does not refresh while disabled', () => {
    renderHook(() => useSessionActivity({ enabled: false }))

    window.dispatchEvent(new Event('pointerdown'))

    expect(refreshSession).not.toHaveBeenCalled()
  })
})
