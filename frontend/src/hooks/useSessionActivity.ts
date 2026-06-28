'use client'

import { useEffect, useRef } from 'react'
import { refreshSession } from '@/src/lib/api/endpoints/auth'

const DEFAULT_SESSION_ACTIVITY_THROTTLE_MS = 5 * 60 * 1000

interface UseSessionActivityOptions {
  enabled: boolean
  throttleMs?: number
}

export function useSessionActivity({
  enabled,
  throttleMs = DEFAULT_SESSION_ACTIVITY_THROTTLE_MS,
}: UseSessionActivityOptions): void {
  const lastRefreshAtRef = useRef<number | null>(null)

  useEffect(() => {
    if (!enabled) return

    const refreshOnActivity = () => {
      if (document.visibilityState === 'hidden') return
      const now = Date.now()
      if (
        lastRefreshAtRef.current !== null
        && now - lastRefreshAtRef.current < throttleMs
      ) {
        return
      }
      lastRefreshAtRef.current = now
      void refreshSession().catch(() => undefined)
    }

    window.addEventListener('pointerdown', refreshOnActivity)
    window.addEventListener('keydown', refreshOnActivity)
    window.addEventListener('focus', refreshOnActivity)
    document.addEventListener('visibilitychange', refreshOnActivity)

    return () => {
      window.removeEventListener('pointerdown', refreshOnActivity)
      window.removeEventListener('keydown', refreshOnActivity)
      window.removeEventListener('focus', refreshOnActivity)
      document.removeEventListener('visibilitychange', refreshOnActivity)
    }
  }, [enabled, throttleMs])
}
