import Link from 'next/link'
import { BrandLockup } from '@/src/components/ui'
import { ROUTES } from '@/src/lib/constants/config'
import { LEGAL_NAV_LINKS, type LegalPageContent } from '@/src/lib/legalContent'

interface LegalPageProps {
  page: LegalPageContent
}

export function LegalPage({ page }: LegalPageProps) {
  return (
    <main className="min-h-dvh bg-bg-page text-fg-1">
      <div className="mx-auto flex w-full max-w-6xl flex-col px-5 py-6 md:px-8 md:py-8">
        <header className="flex items-center gap-4 border-b border-border pb-5">
          <Link
            aria-label="Playbook home"
            className="pb-focus-control rounded-md"
            href={ROUTES.login}
          >
            <BrandLockup markSize={28} />
          </Link>
          <Link
            className="pb-focus-control pb-ui-sm ml-auto rounded-md border border-border-strong px-3 py-2 font-semibold text-fg-2 transition hover:bg-surface-hover hover:text-fg-1"
            href={ROUTES.login}
          >
            Back to login
          </Link>
        </header>

        <section className="border-b border-border py-10 md:py-12">
          <p className="pb-label text-brand">Legal</p>
          <h1 className="pb-h1 mt-3">{page.title}</h1>
          <p className="pb-body mt-4 max-w-3xl text-fg-2">{page.summary}</p>
          <p className="pb-small mt-4">Last updated {page.updatedAt}</p>
        </section>

        <div className="grid gap-8 py-8 lg:grid-cols-[240px_minmax(0,1fr)] lg:gap-12">
          <nav
            aria-label="Legal pages"
            className="self-start border-b border-border pb-5 lg:sticky lg:top-8 lg:border-b-0 lg:border-r lg:pb-0 lg:pr-6"
          >
            <p className="pb-label mb-3 text-fg-3">Pages</p>
            <div className="grid gap-1">
              {LEGAL_NAV_LINKS.map((link) => (
                <Link
                  aria-current={link.slug === page.slug ? 'page' : undefined}
                  className="pb-focus-control pb-ui-sm rounded-md px-3 py-2 font-semibold text-fg-2 transition hover:bg-surface-hover hover:text-fg-1 aria-[current=page]:bg-brand-soft aria-[current=page]:text-brand"
                  href={link.href}
                  key={link.slug}
                >
                  {link.label}
                </Link>
              ))}
            </div>
          </nav>

          <article className="max-w-3xl space-y-9">
            {page.sections.map((section) => (
              <section className="border-b border-border pb-8 last:border-b-0 last:pb-0" key={section.heading}>
                <h2 className="pb-h3">{section.heading}</h2>
                <div className="mt-4 space-y-4">
                  {section.body.map((paragraph) => (
                    <p className="pb-body" key={paragraph}>
                      {paragraph}
                    </p>
                  ))}
                </div>
              </section>
            ))}
          </article>
        </div>
      </div>
    </main>
  )
}
