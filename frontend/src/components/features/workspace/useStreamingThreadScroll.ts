'use client'

import { useCallback, useLayoutEffect, useRef, useState } from 'react'

const AUTO_SCROLL_BOTTOM_THRESHOLD_PX = 96

interface StreamingThreadScrollOptions {
  forceFollowSignal?: string | null
  resetKey?: string | null
  scrollSignal: string
}

export function useStreamingThreadScroll({
  forceFollowSignal = null,
  resetKey = null,
  scrollSignal,
}: StreamingThreadScrollOptions) {
  const threadRef = useRef<HTMLDivElement | null>(null)
  const isPinnedRef = useRef(true)
  const [isPinnedToBottom, setIsPinnedToBottom] = useState(true)

  const setPinnedToBottom = useCallback((isPinned: boolean) => {
    isPinnedRef.current = isPinned
    setIsPinnedToBottom(isPinned)
  }, [])

  const scrollToLatest = useCallback(
    (behavior: ScrollBehavior = 'auto') => {
      const thread = threadRef.current
      if (!thread) return

      const resolvedBehavior = shouldReduceMotion() ? 'auto' : behavior
      if (resolvedBehavior === 'smooth' && typeof thread.scrollTo === 'function') {
        thread.scrollTo({ behavior: resolvedBehavior, top: thread.scrollHeight })
      } else {
        thread.scrollTop = thread.scrollHeight
      }
      setPinnedToBottom(true)
    },
    [setPinnedToBottom],
  )

  const forceFollowLatest = useCallback(
    (behavior: ScrollBehavior = 'auto') => {
      isPinnedRef.current = true
      scrollToLatest(behavior)
    },
    [scrollToLatest],
  )

  const handleScroll = useCallback(() => {
    const thread = threadRef.current
    if (!thread) return
    setPinnedToBottom(isNearBottom(thread))
  }, [setPinnedToBottom])

  useLayoutEffect(() => {
    forceFollowLatest('auto')
  }, [forceFollowLatest, resetKey])

  useLayoutEffect(() => {
    if (forceFollowSignal) {
      forceFollowLatest('auto')
    }
  }, [forceFollowLatest, forceFollowSignal])

  useLayoutEffect(() => {
    if (isPinnedRef.current) {
      scrollToLatest('auto')
    }
  }, [scrollSignal, scrollToLatest])

  return {
    forceFollowLatest,
    handleScroll,
    isPinnedToBottom,
    scrollToLatest,
    threadRef,
  }
}

function isNearBottom(element: HTMLElement): boolean {
  const distanceFromBottom = element.scrollHeight - element.clientHeight - element.scrollTop
  return distanceFromBottom <= AUTO_SCROLL_BOTTOM_THRESHOLD_PX
}

function shouldReduceMotion(): boolean {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
}
