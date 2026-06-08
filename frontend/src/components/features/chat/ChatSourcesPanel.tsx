'use client'

import { FileText, X } from 'lucide-react'
import { cn } from '@/src/lib/utils/cn'
import type { Citation } from '@/src/types/conversations'

interface ChatSourcesPanelProps {
  citations: Citation[]
  onClose: () => void
  onSelectCitation: (citation: Citation) => void
  selectedCitationTitle: string | null
}

export function ChatSourcesPanel({
  citations,
  onClose,
  onSelectCitation,
  selectedCitationTitle,
}: ChatSourcesPanelProps) {
  const selectedCitation = citations.find((citation) => citation.source_title === selectedCitationTitle) ?? citations[0]

  return (
    <aside
      aria-label="Sources"
      className="hidden h-dvh w-[320px] shrink-0 flex-col border-l border-border bg-bg-page text-fg-1 lg:flex"
      role="complementary"
    >
      <header className="flex h-16 shrink-0 items-center border-b border-border px-[18px]">
        <h2 className="text-sm font-bold text-fg-1">Sources</h2>
        <button
          aria-label="Close sources"
          className="ml-auto inline-flex h-[34px] w-[34px] items-center justify-center rounded-sm text-fg-2 transition hover:bg-surface-hover hover:text-fg-1"
          onClick={onClose}
          type="button"
        >
          <X className="h-[18px] w-[18px]" />
        </button>
      </header>

      <div className="flex flex-1 flex-col gap-2.5 overflow-y-auto p-3.5">
        {selectedCitation ? <SelectedSource citation={selectedCitation} /> : null}
        <p className="px-1 py-0.5 text-[11.5px] font-semibold text-fg-3">
          {selectedCitation ? 'All sources' : 'Grounding documents'}
        </p>
        {citations.length > 0 ? (
          citations.map((citation) => (
            <button
              className={cn(
                'flex gap-3 rounded-md border p-3 text-left transition hover:border-border-strong hover:bg-surface-raised',
                citation.source_title === selectedCitation?.source_title
                  ? 'border-border-brand bg-brand-soft'
                  : 'border-border bg-surface',
              )}
              key={citation.id}
              onClick={() => onSelectCitation(citation)}
              type="button"
            >
              <span className="flex h-[30px] w-[30px] shrink-0 items-center justify-center rounded-sm bg-surface-hover text-fg-3">
                <FileText className="h-4 w-4" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-xs text-fg-1">{citation.source_title}</span>
                <span className="mt-0.5 block text-[11.5px] text-fg-3">{formatCitationMeta(citation)}</span>
              </span>
            </button>
          ))
        ) : (
          <p className="rounded-md border border-border bg-surface p-3 text-xs leading-5 text-fg-3">
            Sources will appear here after Playbook grounds an answer in department documents.
          </p>
        )}
      </div>
    </aside>
  )
}

function SelectedSource({ citation }: { citation: Citation }) {
  return (
    <section className="rounded-md border border-border-brand bg-surface p-3.5">
      <div className="mb-2.5 flex items-center gap-2">
        <FileText className="h-3.5 w-3.5 shrink-0 text-brand" />
        <p className="min-w-0 flex-1 truncate text-[11.5px] text-fg-1">{citation.source_title}</p>
        <span className="shrink-0 text-[10px] text-fg-3">{formatPage(citation)}</span>
      </div>
      <p className="mb-2 inline-flex rounded-pill bg-brand-soft px-2 py-1 text-[11px] font-semibold text-brand">
        Selected source
      </p>
      <p className="border-l-2 border-brand pl-3 text-[13px] leading-[1.6] text-fg-2">
        This citation is linked to the assistant answer. Open the source record to review the exact retrieved passage when
        retrieval excerpts are available.
      </p>
    </section>
  )
}

function formatCitationMeta(citation: Citation) {
  const page = formatPage(citation)
  return page ? `${page} · rank ${citation.rank}` : `Rank ${citation.rank}`
}

function formatPage(citation: Citation) {
  const page = citation.source_metadata.page
  return typeof page === 'string' ? page : ''
}
