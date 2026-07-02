import { describe, expect, it } from 'vitest'
import {
  AUTH_PROVIDERS_GC_TIME_MS,
  AUTH_PROVIDERS_STALE_TIME_MS,
  ROUTES,
} from '@/src/lib/constants/config'

describe('config constants', () => {
  it('keeps auth provider config cached longer than default query data', () => {
    expect(AUTH_PROVIDERS_STALE_TIME_MS).toBe(30 * 60 * 1000)
    expect(AUTH_PROVIDERS_GC_TIME_MS).toBe(60 * 60 * 1000)
  })

  it('defines public legal routes for shared link wiring', () => {
    expect(ROUTES.privacy).toBe('/privacy')
    expect(ROUTES.terms).toBe('/terms')
    expect(ROUTES.cookies).toBe('/cookies')
    expect(ROUTES.subprocessors).toBe('/subprocessors')
    expect(ROUTES.security).toBe('/security')
  })
})
