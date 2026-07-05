'use client'

import { useEffect, useMemo, useState } from 'react'
import * as DropdownMenuPrimitive from '@radix-ui/react-dropdown-menu'
import { AlertTriangle, ChevronDown, ChevronLeft, ChevronRight, LoaderCircle, RefreshCw, Sparkles, Zap } from 'lucide-react'
import { AdminPageScaffold } from '@/src/components/features/admin/AdminPageScaffold'
import { AdminQueryReview } from '@/src/components/features/admin/AdminQueryReview'
import {
  dashboardKpis,
  dashboardRiskItems,
  dashboardTopics,
  dashboardVolumeSeries,
  generatedLabel,
  headlineCards,
  unansweredItems,
  windowLabel,
  type DashboardInsightKpi,
  type DashboardRiskItem,
  type DashboardTopicItem,
  type DashboardUnansweredItem,
  type DashboardVolumePoint,
} from '@/src/components/features/admin/adminInsightsView'
import { Button, IconButton } from '@/src/components/ui'
import { cn } from '@/src/lib/utils/cn'
import type {
  AdminAnalyticsQuery,
  AdminAnalyticsQueryFilters,
  AdminAnalyticsSummary,
  AdminTimeWindow,
  DashboardInsight,
  DashboardInsightRun,
} from '@/src/types/adminAnalytics'

interface AdminInsightsDashboardProps {
  currentInsight: DashboardInsight | null
  currentRun: DashboardInsightRun | null
  isChatOpen: boolean
  isError: boolean
  isQueryReviewFetching: boolean
  isGenerating: boolean
  isLoading: boolean
  onGenerate: () => void
  onOpenChat: () => void
  onQueryPageChange: (page: number) => void
  onQueryFiltersChange: (filters: Required<AdminAnalyticsQueryFilters>) => void
  onTimeWindowChange: (window: AdminTimeWindow) => void
  queries: AdminAnalyticsQuery[]
  queryHasNextPage: boolean
  queryFilters: Required<AdminAnalyticsQueryFilters>
  queryPage: number
  queryPageSize: number
  summary: AdminAnalyticsSummary | null
  timeWindow: AdminTimeWindow
}

const timeWindowOptions: Array<{ label: string; value: AdminTimeWindow }> = [
  { label: 'Last 7 days', value: '7d' },
  { label: 'Last 30 days', value: '30d' },
]

const timeWindowLabels = Object.fromEntries(
  timeWindowOptions.map((option) => [option.value, option.label]),
) as Record<AdminTimeWindow, string>

const headerControlClassName = 'pb-admin-header-control pb-ui-sm'

export function AdminInsightsDashboard({
  currentInsight,
  currentRun,
  isChatOpen,
  isError,
  isQueryReviewFetching,
  isGenerating,
  isLoading,
  onGenerate,
  onOpenChat,
  onQueryPageChange,
  onQueryFiltersChange,
  onTimeWindowChange,
  queries,
  queryHasNextPage,
  queryFilters,
  queryPage,
  queryPageSize,
  summary,
  timeWindow,
}: AdminInsightsDashboardProps) {
  const insight = currentRun?.output ?? currentInsight
  const hasFailedRun = currentRun?.status === 'failed'
  const topics = dashboardTopics(summary)
  const risks = dashboardRiskItems(summary, insight)
  const kpis = dashboardKpis(summary)
  const volumeSeries = dashboardVolumeSeries(summary)

  return (
    <AdminPageScaffold
      actions={
        <>
          <TimeWindowMenu onChange={onTimeWindowChange} value={timeWindow} />
          <Button
            className={cn(headerControlClassName, 'pb-admin-insights-regenerate-control')}
            disabled={isGenerating}
            onClick={onGenerate}
            size="sm"
            variant="secondary"
          >
            {isGenerating ? <LoaderCircle className="h-[15px] w-[15px] pb-spin" /> : <RefreshCw className="h-[15px] w-[15px]" />}
            {isGenerating ? 'Regenerating...' : 'Regenerate'}
          </Button>
          <Button className={headerControlClassName} disabled={isChatOpen} onClick={onOpenChat} size="sm">
            <Zap className="h-[15px] w-[15px]" />
            Explore with AI
          </Button>
        </>
      }
      subtitle="AI generated insights from user queries"
      title="Insights"
    >
      {isError && (
        <p className="pb-admin-table-text mb-3 rounded-md border border-danger/30 bg-danger-bg px-3 py-2 text-danger">
          Dashboard insights could not be loaded. Try refreshing the page.
        </p>
      )}
      <AISummaryCard
        failedMessage={hasFailedRun ? currentRun?.error_message ?? 'Dashboard insight generation failed.' : null}
        generatedMeta={`${generatedLabel(insight)} · ${windowLabel(summary)}`}
        insight={insight}
        isLoading={isLoading}
        kpis={kpis}
        unanswered={unansweredItems(insight)}
      />
      <div className="mt-3.5 grid items-stretch gap-4 lg:grid-cols-[1.55fr_1fr]">
        <DashboardCard className="h-full" title="Common topics">
          <div className="pb-dashboard-breakdown-scroll">
            <TopicBars items={topics} />
          </div>
        </DashboardCard>
        <DashboardCard className="h-full" title="Risk flags">
          <div className="pb-dashboard-breakdown-scroll">
            <RiskFlags items={risks} />
          </div>
        </DashboardCard>
      </div>
      <QueryVolumePanel
        queryVolume={summary?.query_volume ?? 0}
        series={volumeSeries}
        timeWindow={timeWindow}
      />
      <AdminQueryReview
        filters={queryFilters}
        hasNextPage={queryHasNextPage}
        isFetching={isQueryReviewFetching}
        onPageChange={onQueryPageChange}
        onFiltersChange={onQueryFiltersChange}
        page={queryPage}
        pageSize={queryPageSize}
        queries={queries}
        summary={summary}
      />
    </AdminPageScaffold>
  )
}

interface TimeWindowMenuProps {
  onChange: (window: AdminTimeWindow) => void
  value: AdminTimeWindow
}

function TimeWindowMenu({ onChange, value }: TimeWindowMenuProps) {
  return (
    <DropdownMenuPrimitive.Root>
      <DropdownMenuPrimitive.Trigger asChild>
        <button
          className={cn(
            headerControlClassName,
            'inline-flex items-center gap-2 rounded-md border border-border-strong bg-surface font-semibold text-fg-1 transition hover:bg-surface-hover',
          )}
          type="button"
        >
          {timeWindowLabels[value]}
          <ChevronDown className="h-[15px] w-[15px] text-fg-3" />
        </button>
      </DropdownMenuPrimitive.Trigger>
      <DropdownMenuPrimitive.Portal>
        <DropdownMenuPrimitive.Content
          align="end"
          className="pb-ui-sm z-50 min-w-[172px] rounded-md border border-border-strong bg-surface-raised p-1.5 text-fg-2 shadow-lg"
          sideOffset={8}
        >
          {timeWindowOptions.map((option) => (
            <DropdownMenuPrimitive.Item
              className="pb-focus-item cursor-pointer rounded-sm px-2.5 py-2 transition"
              key={option.value}
              onSelect={() => onChange(option.value)}
            >
              {option.label}
            </DropdownMenuPrimitive.Item>
          ))}
        </DropdownMenuPrimitive.Content>
      </DropdownMenuPrimitive.Portal>
    </DropdownMenuPrimitive.Root>
  )
}

interface AISummaryCardProps {
  failedMessage: string | null
  generatedMeta: string
  insight: DashboardInsight | null
  isLoading: boolean
  kpis: DashboardInsightKpi[]
  unanswered: DashboardUnansweredItem[]
}

function AISummaryCard({
  failedMessage,
  generatedMeta,
  insight,
  isLoading,
  kpis,
  unanswered,
}: AISummaryCardProps) {
  const [open, setOpen] = useState(false)
  const loading = isLoading

  return (
    <section className="pb-dashboard-summary-card">
      <div className="mb-3 flex items-center gap-2.5">
        <span className="pb-dashboard-section-label inline-flex items-center gap-2 font-bold text-brand">
          <Sparkles className="h-4 w-4" />
          AI summary
        </span>
        <span className="pb-dashboard-meta ml-auto inline-flex items-center gap-2">
          {failedMessage ? (
            <>
              <AlertTriangle className="h-3.5 w-3.5 text-danger" />
              Failed
            </>
          ) : loading ? (
            'Loading summary'
          ) : (
            <>
              <span className="pb-pulse h-1.5 w-1.5 rounded-full bg-success [--pulse-color:rgba(63,182,139,0.4)]" />
              {generatedMeta}
            </>
          )}
        </span>
      </div>
      {failedMessage ? (
        <p className="pb-dashboard-summary-text text-danger">{failedMessage}</p>
      ) : loading ? (
        <div className="grid gap-2.5">
          <span className="h-3.5 w-[92%] rounded-pill bg-surface-raised" />
          <span className="h-3.5 w-full rounded-pill bg-surface-raised" />
          <span className="h-3.5 w-[70%] rounded-pill bg-surface-raised" />
        </div>
      ) : !insight ? (
        <p className="pb-dashboard-summary-text">
          No dashboard insight has been generated for this window yet.
        </p>
      ) : (
        <>
          <p className="pb-dashboard-summary-text">{insight.summary}</p>
          <div className="mt-3.5 grid border-t border-border pt-3.5 md:grid-cols-3">
            {kpis.map((kpi, index) => (
              <div
                className={cn('min-w-0', index > 0 && 'mt-4 border-t border-border pt-4 md:mt-0 md:border-l md:border-t-0 md:pl-6 md:pt-0')}
                key={kpi.label}
              >
                <div className="flex items-baseline gap-2">
                  <span className="pb-dashboard-kpi-value">{kpi.value}</span>
                  <span className="pb-dashboard-kpi-label">{kpi.label}</span>
                </div>
                <p className="pb-dashboard-meta mt-1.5 text-fg-4">{kpi.sub}</p>
              </div>
            ))}
          </div>
          <button
            className="pb-focus-control mt-3 inline-flex items-center gap-1.5 rounded-sm border border-transparent pb-dashboard-row-label font-semibold text-brand transition hover:text-brand-hover"
            onClick={() => setOpen((current) => !current)}
            type="button"
          >
            {open ? 'Hide details' : 'Show details'}
            <ChevronDown className={cn('h-[15px] w-[15px] transition', open && 'rotate-180')} />
          </button>
          {open && (
            <div className="animate-pb-fade">
              <div className="mt-4 flex flex-wrap gap-2">
                {headlineCards(insight).map((card) => (
                  <span className="inline-flex items-center gap-2 rounded-pill border border-border bg-bg-base px-3 py-1.5" key={card.title}>
                    <span className={cn('h-[7px] w-[7px] rounded-full', severityDotClass(card.severity ?? 'medium'))} />
                    <span className="pb-dashboard-row-label font-semibold text-fg-1">{card.title}</span>
                    <span className="pb-dashboard-meta">{card.value}</span>
                  </span>
                ))}
              </div>
              <div className="mt-[18px] border-t border-border pt-4">
                <p className="pb-dashboard-section-label mb-3">Recommended focus</p>
                <div className="grid gap-3 md:grid-cols-2">
                  {insight.recommended_attention_areas.map((area, index) => (
                    <div className="flex items-start gap-3" key={area}>
                      <span className="pb-admin-small-badge mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-sm bg-brand-soft p-0 font-display text-brand">
                        {index + 1}
                      </span>
                      <p className="pb-dashboard-row-label leading-normal">{area}</p>
                    </div>
                  ))}
                </div>
              </div>
              {unanswered.length > 0 && (
                <div className="mt-[18px] border-t border-border pt-4">
                  <p className="pb-dashboard-section-label mb-3">Response gaps</p>
                  <div className="grid gap-2.5">
                    {unanswered.slice(0, 5).map((item) => (
                      <div className="rounded-md border border-border bg-bg-base px-3 py-2" key={item.id}>
                        <p className="pb-dashboard-row-label text-fg-1">{item.text}</p>
                        <p className="pb-dashboard-meta mt-1 text-fg-4">{item.reason}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </section>
  )
}

interface DashboardCardProps {
  children: React.ReactNode
  className?: string
  title: string
  titleAside?: React.ReactNode
}

function DashboardCard({ children, className, title, titleAside }: DashboardCardProps) {
  return (
    <section className={cn('pb-dashboard-card', className)}>
      <div className="mb-3 flex items-center">
        <h2 className="pb-card-title">{title}</h2>
        {titleAside && <div className="ml-auto">{titleAside}</div>}
      </div>
      {children}
    </section>
  )
}

function TopicBars({ items }: { items: DashboardTopicItem[] }) {
  if (items.length === 0) {
    return <p className="pb-admin-table-text text-fg-3">No topic data for this window.</p>
  }
  const max = Math.max(...items.map((item) => item.count), 1)
  return (
    <div className="grid gap-2.5">
      {items.map((item) => (
        <div className="grid grid-cols-[92px_1fr_34px] items-center gap-3" key={item.key}>
          <span className="pb-dashboard-row-label truncate font-medium">{item.label}</span>
          <span className="h-[9px] overflow-hidden rounded-pill bg-surface-raised">
            <span
              className="block h-full rounded-pill bg-orange-600"
              style={{ width: `${Math.round((item.count / max) * 100)}%` }}
            />
          </span>
          <span className="pb-dashboard-row-label text-right">{item.count}</span>
        </div>
      ))}
    </div>
  )
}

function RiskFlags({ items }: { items: DashboardRiskItem[] }) {
  if (items.length === 0) {
    return <p className="pb-admin-table-text text-fg-3">No risk labels for this window.</p>
  }
  return (
    <div className="grid gap-0.5">
      {items.map((risk, index) => (
        <div
          className={cn('flex items-center gap-3 px-1 py-3.5', index < items.length - 1 && 'border-b border-border')}
          key={risk.label}
        >
          <span className={cn('h-2 w-2 shrink-0 rounded-full', severityDotClass(risk.severity))} />
          <span className="pb-admin-table-text flex-1 text-fg-1">{risk.label}</span>
          <span className={cn('pb-admin-small-badge', severityTextClass(risk.severity))}>
            {risk.severity}
          </span>
          <span className="pb-dashboard-count w-8 text-right">{risk.count}</span>
        </div>
      ))}
    </div>
  )
}

const QUERY_VOLUME_PAGE_SIZE = 7

interface QueryVolumePanelProps {
  queryVolume: number
  series: DashboardVolumePoint[]
  timeWindow: AdminTimeWindow
}

function QueryVolumePanel({ queryVolume, series, timeWindow }: QueryVolumePanelProps) {
  const pages = useMemo(() => volumeWeekPages(series), [series])
  const latestPageIndex = Math.max(pages.length - 1, 0)
  const [pageIndex, setPageIndex] = useState(latestPageIndex)
  const hasPagination = timeWindow === '30d' && pages.length > 1

  useEffect(() => {
    setPageIndex(latestPageIndex)
  }, [latestPageIndex, timeWindow])

  const visibleSeries = hasPagination
    ? pages[pageIndex] ?? []
    : series.slice(-QUERY_VOLUME_PAGE_SIZE)
  const titleAside = hasPagination ? (
    <div className="flex items-center gap-1.5">
      <IconButton
        aria-label="Previous query-volume week"
        disabled={pageIndex === 0}
        onClick={() => setPageIndex((current) => Math.max(0, current - 1))}
        size="sm"
        variant="ghost"
      >
        <ChevronLeft className="h-3.5 w-3.5" />
      </IconButton>
      <IconButton
        aria-label="Next query-volume week"
        disabled={pageIndex >= pages.length - 1}
        onClick={() => setPageIndex((current) => Math.min(pages.length - 1, current + 1))}
        size="sm"
        variant="ghost"
      >
        <ChevronRight className="h-3.5 w-3.5" />
      </IconButton>
    </div>
  ) : null

  return (
    <DashboardCard className="mt-3.5" title="Query volume" titleAside={titleAside}>
      <QueryVolumeChart queryVolume={queryVolume} series={visibleSeries} />
    </DashboardCard>
  )
}

function QueryVolumeChart({ queryVolume, series }: { queryVolume: number; series: DashboardVolumePoint[] }) {
  if (series.length === 0) {
    return <p className="pb-admin-table-text text-fg-3">No query volume data for this window.</p>
  }
  const max = Math.max(...series.map((point) => point.total), 1)
  return (
    <div>
      <div className="flex h-[116px] items-end gap-3 px-0.5">
        {series.map((point) => {
          const height = Math.round((point.total / max) * 100) + 4
          const unansweredHeight = Math.round((point.unanswered / max) * 100)
          return (
            <div className="flex flex-1 flex-col items-center gap-2" key={point.key}>
              <span
                aria-label={`${point.date}: ${point.total} questions`}
                className="relative w-full max-w-10 overflow-hidden rounded-t bg-brand"
                style={{ height }}
              >
                {unansweredHeight > 0 && <span className="absolute inset-x-0 top-0 bg-warning" style={{ height: unansweredHeight }} />}
              </span>
              <span className="pb-dashboard-meta font-medium text-fg-4">{point.day}</span>
            </div>
          )
        })}
      </div>
      <div className="mt-2.5 flex items-center gap-4 border-t border-border pt-2.5">
        <Legend colorClass="bg-brand" label="Answered" />
        <Legend colorClass="bg-warning" label="Unanswered / declined" />
        <span className="pb-ui-xs ml-auto text-fg-3">{queryVolume} in window</span>
      </div>
    </div>
  )
}

function volumeWeekPages(series: DashboardVolumePoint[]): DashboardVolumePoint[][] {
  const pages: DashboardVolumePoint[][] = []
  for (let end = series.length; end > 0; end -= QUERY_VOLUME_PAGE_SIZE) {
    pages.unshift(series.slice(Math.max(0, end - QUERY_VOLUME_PAGE_SIZE), end))
  }
  return pages
}

function Legend({ colorClass, label }: { colorClass: string; label: string }) {
  return (
    <span className="pb-dashboard-meta inline-flex items-center gap-2">
      <span className={cn('h-[9px] w-[9px] rounded-sm', colorClass)} />
      {label}
    </span>
  )
}

function severityDotClass(severity: 'low' | 'medium' | 'high') {
  if (severity === 'high') return 'bg-danger'
  if (severity === 'medium') return 'bg-warning'
  return 'bg-success'
}

function severityTextClass(severity: 'low' | 'medium' | 'high') {
  if (severity === 'high') return 'text-danger'
  if (severity === 'medium') return 'text-warning'
  return 'text-success'
}
