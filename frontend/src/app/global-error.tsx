'use client'

import { useEffect } from 'react'
import * as Sentry from '@sentry/nextjs'

type GlobalErrorProps = {
  error: Error & { digest?: string }
  reset: () => void
}

export default function GlobalError({ error, reset }: GlobalErrorProps) {
  useEffect(() => {
    Sentry.captureException(error)
  }, [error])

  return (
    <html lang="en">
      <body>
        <main className="flex min-h-dvh items-center justify-center bg-bg-page px-6 text-fg-1">
          <section className="w-full max-w-md space-y-5">
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase text-fg-3">
                Playbook
              </p>
              <h1 className="font-display text-3xl font-semibold">
                Something went wrong.
              </h1>
              <p className="text-sm leading-6 text-fg-2">
                Refresh the page or try again shortly.
              </p>
            </div>
            <button
              type="button"
              onClick={reset}
              className="min-h-11 rounded-md bg-brand px-4 py-2 text-sm font-semibold text-fg-on-brand transition hover:bg-brand-hover focus-visible:outline-none"
            >
              Try again
            </button>
          </section>
        </main>
      </body>
    </html>
  )
}
