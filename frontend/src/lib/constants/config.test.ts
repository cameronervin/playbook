import { describe, expect, it } from 'vitest'
import {
  AUTH_PROVIDERS_GC_TIME_MS,
  AUTH_PROVIDERS_STALE_TIME_MS,
} from '@/src/lib/constants/config'

describe('config constants', () => {
  it('keeps auth provider config cached longer than default query data', () => {
    expect(AUTH_PROVIDERS_STALE_TIME_MS).toBe(30 * 60 * 1000)
    expect(AUTH_PROVIDERS_GC_TIME_MS).toBe(60 * 60 * 1000)
  })
})
