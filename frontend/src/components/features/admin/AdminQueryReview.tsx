'use client'

import { useMemo, useState } from 'react'
import { ChevronDown, ChevronLeft, ChevronRight, FilterX } from 'lucide-react'
import {
  queryReviewFilterOptions,
  type QueryReviewFilterOption,
} from '@/src/components/features/admin/adminInsightsView'
import { cn } from '@/src/lib/utils/cn'
import type {
  AdminAnalyticsQuery,
  AdminAnalyticsQueryFilters,
  AdminAnalyticsSummary,
} from '@/src/types/adminAnalytics'

interface AdminQueryReviewProps {
  filters: Required<AdminAnalyticsQueryFilters>
  hasNextPage: boolean
  isFetching: boolean
  onPageChange: (page: number) => void
  onFiltersChange: (filters: Required<AdminAnalyticsQueryFilters>) => void
  page: number
  pageSize: number
  queries: AdminAnalyticsQuery[]
  summary: AdminAnalyticsSummary | null
}

type QueryFilterKind = 'topic' | 'risk'

const QUERY_DATE_FORMATTER = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
})

export function AdminQueryReview({
  filters,
  hasNextPage,
  isFetching,
  onPageChange,
  onFiltersChange,
  page,
  pageSize,
  queries,
  summary,
}: AdminQueryReviewProps) {
  const [openMessageId, setOpenMessageId] = useState<string | null>(null)
  const options = useMemo(() => queryReviewFilterOptions(summary, filters), [summary, filters])
  const hasFilters = filters.topic_labels.length > 0 || filters.risk_labels.length > 0
  const firstRow = queries.length > 0 ? page * pageSize + 1 : 0
  const lastRow = page * pageSize + queries.length

  const toggleFilter = (kind: QueryFilterKind, label: string) => {
    const field = kind === 'topic' ? 'topic_labels' : 'risk_labels'
    const current = filters[field]
    const next = current.includes(label)
      ? current.filter((item) => item !== label)
      : [...current, label]
    onFiltersChange({ ...filters, [field]: next })
  }

  return (
    <section aria-labelledby="admin-query-review-title" className="pb-dashboard-card mt-3.5">
      <div className="mb-3 flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <h2 className="pb-card-title" id="admin-query-review-title">Query review</h2>
          <p className="pb-dashboard-meta mt-1 text-fg-3">
            Anonymized athlete questions in the selected window.
          </p>
        </div>
        {hasFilters && (
          <button
            className="pb-focus-control inline-flex items-center gap-1.5 rounded-md border border-border bg-surface px-2.5 py-1.5 pb-dashboard-row-label font-semibold text-fg-2 transition hover:bg-surface-hover hover:text-fg-1"
            onClick={() => onFiltersChange({ topic_labels: [], risk_labels: [] })}
            type="button"
          >
            <FilterX className="h-3.5 w-3.5" />
            Clear filters
          </button>
        )}
      </div>
      <QueryFilterGroup
        active={filters.topic_labels}
        kind="topic"
        onToggle={toggleFilter}
        options={options.topics}
      />
      <QueryFilterGroup
        active={filters.risk_labels}
        className="mt-2"
        kind="risk"
        onToggle={toggleFilter}
        options={options.risks}
      />
      <div className="mt-4 overflow-hidden rounded-md border border-border">
        {queries.length === 0 ? (
          <p className="pb-admin-table-text bg-bg-base px-3 py-4 text-fg-3">
            No matching query rows for this window.
          </p>
        ) : (
          queries.map((query, index) => (
            <QueryReviewRow
              isOpen={openMessageId === query.message_id}
              key={query.message_id}
              onToggle={() =>
                setOpenMessageId((current) =>
                  current === query.message_id ? null : query.message_id,
                )
              }
              query={query}
              showDivider={index < queries.length - 1}
            />
          ))
        )}
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <span className="pb-dashboard-meta text-fg-3">
          {queries.length > 0 ? `${firstRow}-${lastRow}` : '0'} shown
          {isFetching ? ' · Updating...' : ''}
        </span>
        <div className="ml-auto flex items-center gap-2">
          <button
            aria-label="Previous query page"
            className="pb-focus-control inline-flex h-8 items-center gap-1.5 rounded-md border border-border bg-surface px-2.5 pb-dashboard-row-label font-semibold text-fg-2 transition hover:bg-surface-hover hover:text-fg-1 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={page === 0 || isFetching}
            onClick={() => onPageChange(Math.max(0, page - 1))}
            type="button"
          >
            <ChevronLeft className="h-3.5 w-3.5" />
            Previous
          </button>
          <span className="pb-dashboard-meta min-w-12 text-center text-fg-3">
            Page {page + 1}
          </span>
          <button
            aria-label="Next query page"
            className="pb-focus-control inline-flex h-8 items-center gap-1.5 rounded-md border border-border bg-surface px-2.5 pb-dashboard-row-label font-semibold text-fg-2 transition hover:bg-surface-hover hover:text-fg-1 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={!hasNextPage || isFetching}
            onClick={() => onPageChange(page + 1)}
            type="button"
          >
            Next
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </section>
  )
}

interface QueryFilterGroupProps {
  active: string[]
  className?: string
  kind: QueryFilterKind
  onToggle: (kind: QueryFilterKind, label: string) => void
  options: QueryReviewFilterOption[]
}

function QueryFilterGroup({
  active,
  className,
  kind,
  onToggle,
  options,
}: QueryFilterGroupProps) {
  if (options.length === 0) return null
  return (
    <div className={cn('flex flex-wrap items-center gap-2', className)}>
      <span className="pb-dashboard-section-label mr-1 text-fg-3">
        {kind === 'topic' ? 'Topics' : 'Risks'}
      </span>
      {options.map((option) => {
        const selected = active.includes(option.key)
        return (
          <button
            aria-label={`${selected ? 'Remove' : 'Filter'} ${kind} ${option.label}`}
            className={cn(
              'pb-focus-control inline-flex items-center gap-1.5 rounded-pill border px-2.5 py-1 pb-dashboard-meta font-semibold transition',
              selected
                ? 'border-brand bg-brand-soft text-brand'
                : 'border-border bg-bg-base text-fg-3 hover:border-border-strong hover:bg-surface-hover hover:text-fg-1',
            )}
            key={option.key}
            onClick={() => onToggle(kind, option.key)}
            type="button"
          >
            {option.label}
            <span className="text-fg-4">{option.count}</span>
          </button>
        )
      })}
    </div>
  )
}

interface QueryReviewRowProps {
  isOpen: boolean
  onToggle: () => void
  query: AdminAnalyticsQuery
  showDivider: boolean
}

function QueryReviewRow({ isOpen, onToggle, query, showDivider }: QueryReviewRowProps) {
  return (
    <article className={cn('bg-bg-base', showDivider && 'border-b border-border')}>
      <button
        aria-label={`${isOpen ? 'Close' : 'Open'} query details for ${query.text}`}
        className="pb-focus-control flex w-full items-start gap-3 px-3 py-3 text-left transition hover:bg-surface/50"
        onClick={onToggle}
        type="button"
      >
        <ChevronDown className={cn('mt-0.5 h-4 w-4 shrink-0 text-fg-4 transition', isOpen && 'rotate-180 text-brand')} />
        <span className="min-w-0 flex-1">
          <span className="pb-admin-table-text block text-fg-1">{query.text}</span>
          <span className="pb-admin-table-meta mt-1 flex flex-wrap gap-x-3 gap-y-1 text-fg-3">
            <span>{query.anonymous_user_key}</span>
            <span>{formatDate(query.created_at)}</span>
            <span>{query.unanswered_reason ? 'Unanswered' : 'Answered'}</span>
          </span>
        </span>
      </button>
      {isOpen && (
        <div className="animate-pb-fade border-t border-border bg-surface/40 px-6 py-3">
          <div className="grid gap-2 md:grid-cols-2">
            <DetailLine label="Owner" value={query.anonymous_user_key} />
            <DetailLine label="Message" value={query.message_id} />
            <DetailLine label="Answer" value={formatValue(query.answer_type)} />
            <DetailLine label="Response" value={formatValue(query.response_status)} />
            <DetailLine label="Reason" value={formatValue(query.unanswered_reason)} />
            <DetailLine label="Created" value={formatDate(query.created_at)} />
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {[...query.topic_labels, ...query.risk_labels].map((label) => (
              <span
                className="rounded-pill border border-border bg-bg-base px-2 py-1 pb-dashboard-meta font-semibold text-fg-2"
                key={label}
              >
                {formatValue(label)}
              </span>
            ))}
          </div>
        </div>
      )}
    </article>
  )
}

function DetailLine({ label, value }: { label: string; value: string }) {
  return (
    <p aria-label={`${label} ${value}`} className="pb-admin-table-meta text-fg-3">
      {label} <span className="font-semibold text-fg-1">{value}</span>
    </p>
  )
}

function formatDate(value: string): string {
  return QUERY_DATE_FORMATTER.format(new Date(value))
}

function formatValue(value: string | null): string {
  if (!value) return 'none'
  return value.replace(/[-_]+/g, ' ')
}
