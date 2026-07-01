'use client'

import { useState } from 'react'
import * as DropdownMenuPrimitive from '@radix-ui/react-dropdown-menu'
import { AlertTriangle, ChevronDown, LoaderCircle, RefreshCw, Sparkles, Zap } from 'lucide-react'
import { AdminPageScaffold } from '@/src/components/features/admin/AdminPageScaffold'
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
import { Button } from '@/src/components/ui'
import { cn } from '@/src/lib/utils/cn'
import type {
  AdminAnalyticsQuery,
  AdminAnalyticsSummary,
  AdminTimeWindow,
  DashboardInsight,
  DashboardInsightRun,
} from '@/src/types/adminAnalytics'

interface AdminInsightsDashboardProps {
  currentInsight: DashboardInsight | null
  currentRun: DashboardInsightRun | null
  isError: boolean
  isGenerating: boolean
  isLoading: boolean
  onGenerate: () => void
  onOpenChat: () => void
  onTimeWindowChange: (window: AdminTimeWindow) => void
  queries: AdminAnalyticsQuery[]
  summary: AdminAnalyticsSummary | null
  timeWindow: AdminTimeWindow
}

const timeWindowLabels: Record<AdminTimeWindow, string> = {
  '7d': 'Last 7 days',
  '30d': 'Last 30 days',
  custom: 'Custom range',
}

const headerControlClassName = 'pb-admin-header-control pb-ui-sm'

export function AdminInsightsDashboard({
  currentInsight,
  currentRun,
  isError,
  isGenerating,
  isLoading,
  onGenerate,
  onOpenChat,
  onTimeWindowChange,
  queries,
  summary,
  timeWindow,
}: AdminInsightsDashboardProps) {
  const insight = currentRun?.output ?? currentInsight
  const hasFailedRun = currentRun?.status === 'failed'
  const topics = dashboardTopics(summary)
  const risks = dashboardRiskItems(summary, insight)
  const kpis = dashboardKpis(summary)
  const volumeSeries = dashboardVolumeSeries(summary, queries)

  return (
    <AdminPageScaffold
      actions={
        <>
          <TimeWindowMenu onChange={onTimeWindowChange} value={timeWindow} />
          <Button
            className={headerControlClassName}
            disabled={isGenerating || timeWindow === 'custom'}
            onClick={onGenerate}
            size="sm"
            variant="secondary"
          >
            {isGenerating ? <LoaderCircle className="h-[15px] w-[15px] pb-spin" /> : <RefreshCw className="h-[15px] w-[15px]" />}
            {isGenerating ? 'Regenerating...' : 'Regenerate'}
          </Button>
          <Button className={headerControlClassName} onClick={onOpenChat} size="sm">
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
        isGenerating={isGenerating}
        isLoading={isLoading}
        kpis={kpis}
        unanswered={unansweredItems(insight)}
      />
      <div className="mt-3.5 grid gap-4 lg:grid-cols-[1.55fr_1fr]">
        <DashboardCard title="Common topics">
          <TopicBars items={topics} />
        </DashboardCard>
        <DashboardCard title="Risk flags">
          <RiskFlags items={risks} />
        </DashboardCard>
      </div>
      <DashboardCard className="mt-3.5" title="Query volume" titleAside={`${summary?.query_volume ?? 0} in window`}>
        <QueryVolumeChart series={volumeSeries} />
      </DashboardCard>
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
            'inline-flex items-center gap-2 rounded-md border border-border-strong bg-surface px-3 font-semibold text-fg-1 transition hover:bg-surface-hover',
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
          {(Object.keys(timeWindowLabels) as AdminTimeWindow[]).map((window) => (
            <DropdownMenuPrimitive.Item
              className="pb-focus-item cursor-pointer rounded-sm px-2.5 py-2 transition"
              disabled={window === 'custom'}
              key={window}
              onSelect={() => onChange(window)}
            >
              {timeWindowLabels[window]}
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
  isGenerating: boolean
  isLoading: boolean
  kpis: DashboardInsightKpi[]
  unanswered: DashboardUnansweredItem[]
}

function AISummaryCard({
  failedMessage,
  generatedMeta,
  insight,
  isGenerating,
  isLoading,
  kpis,
  unanswered,
}: AISummaryCardProps) {
  const [open, setOpen] = useState(false)
  const loading = isLoading || isGenerating

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
            <>
              <LoaderCircle className="h-3.5 w-3.5 pb-spin text-info" />
              Generating...
            </>
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
  titleAside?: string
}

function DashboardCard({ children, className, title, titleAside }: DashboardCardProps) {
  return (
    <section className={cn('pb-dashboard-card', className)}>
      <div className="mb-3 flex items-baseline">
        <h2 className="pb-card-title">{title}</h2>
        {titleAside && <span className="pb-ui-xs ml-auto text-fg-3">{titleAside}</span>}
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

function QueryVolumeChart({ series }: { series: DashboardVolumePoint[] }) {
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
            <div className="flex flex-1 flex-col items-center gap-2" key={point.date}>
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
      </div>
    </div>
  )
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
