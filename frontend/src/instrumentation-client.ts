import * as Sentry from '@sentry/nextjs'

import {
  resolveSentryTracesSampleRate,
  scrubSentryEvent,
} from '@/src/lib/observability/sentry'

const sentryDsn = process.env.NEXT_PUBLIC_SENTRY_DSN

if (sentryDsn) {
  Sentry.init({
    dsn: sentryDsn,
    environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT || process.env.NODE_ENV,
    release: process.env.NEXT_PUBLIC_SENTRY_RELEASE || undefined,
    sendDefaultPii: false,
    enableLogs: false,
    tracesSampleRate: resolveSentryTracesSampleRate(
      process.env.NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE,
    ),
    beforeSend: scrubSentryEvent,
    beforeSendTransaction: scrubSentryEvent,
  })
}
