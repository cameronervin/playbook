import { describe, expect, it } from 'vitest'

import {
  DEFAULT_SENTRY_TRACES_SAMPLE_RATE,
  SENTRY_REDACTION,
  resolveSentryTracesSampleRate,
  scrubSentryEvent,
} from './sentry'

describe('resolveSentryTracesSampleRate', () => {
  it('defaults to the production-safe sample rate when unset or invalid', () => {
    expect(resolveSentryTracesSampleRate(undefined)).toBe(
      DEFAULT_SENTRY_TRACES_SAMPLE_RATE,
    )
    expect(resolveSentryTracesSampleRate('')).toBe(DEFAULT_SENTRY_TRACES_SAMPLE_RATE)
    expect(resolveSentryTracesSampleRate('not-a-number')).toBe(
      DEFAULT_SENTRY_TRACES_SAMPLE_RATE,
    )
  })

  it('accepts explicit rates and clamps out-of-range values', () => {
    expect(resolveSentryTracesSampleRate('0')).toBe(0)
    expect(resolveSentryTracesSampleRate('0.25')).toBe(0.25)
    expect(resolveSentryTracesSampleRate('1')).toBe(1)
    expect(resolveSentryTracesSampleRate('-0.5')).toBe(0)
    expect(resolveSentryTracesSampleRate('2')).toBe(1)
  })
})

describe('scrubSentryEvent', () => {
  it('removes PII, request bodies, auth headers, prompts, and signed URLs', () => {
    const event = {
      user: {
        email: 'athlete@example.edu',
        ip_address: '203.0.113.10',
      },
      request: {
        headers: {
          Authorization: 'Bearer token-secret',
          Cookie: 'session=secret',
          'X-Forwarded-For': '203.0.113.10',
          'X-Request-ID': 'req-1',
        },
        query_string: 'token=token-secret&safe=1',
        data: { prompt: 'where is the NIL policy?' },
        cookies: { session: 'secret' },
      },
      extra: {
        prompt: 'student prompt',
        source_text: 'policy source text',
        source_uri: 'https://bucket/file.pdf?X-Amz-Signature=secret',
        presigned_url: 'https://bucket/file.pdf?token=secret',
        vars: { api_key: 'sk-secret' },
        client_ip: '203.0.113.10',
        safe_id: 'org-123',
      },
    }

    const scrubbed = scrubSentryEvent(event)

    expect(scrubbed).not.toBeNull()
    expect(JSON.stringify(scrubbed)).not.toContain('athlete@example.edu')
    expect(JSON.stringify(scrubbed)).not.toContain('203.0.113.10')
    expect(JSON.stringify(scrubbed)).not.toContain('token-secret')
    expect(JSON.stringify(scrubbed)).not.toContain('student prompt')
    expect(JSON.stringify(scrubbed)).not.toContain('policy source text')
    expect(JSON.stringify(scrubbed)).not.toContain('sk-secret')
    expect(scrubbed?.user).toBeUndefined()
    expect(scrubbed?.request?.data).toBeUndefined()
    expect(scrubbed?.request?.cookies).toBeUndefined()
    expect(scrubbed?.request?.query_string).toBe(SENTRY_REDACTION)
    expect(scrubbed?.request?.headers?.Authorization).toBe(SENTRY_REDACTION)
    expect(scrubbed?.request?.headers?.Cookie).toBe(SENTRY_REDACTION)
    expect(scrubbed?.request?.headers?.['X-Forwarded-For']).toBe(SENTRY_REDACTION)
    expect(scrubbed?.extra?.safe_id).toBe('org-123')
  })
})
