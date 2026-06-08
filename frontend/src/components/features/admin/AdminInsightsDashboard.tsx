'use client'

import { useState } from 'react'
import * as DropdownMenuPrimitive from '@radix-ui/react-dropdown-menu'
import { ChevronDown, LoaderCircle, RefreshCw, Sparkles, Zap } from 'lucide-react'
import { AdminPageScaffold } from '@/src/components/features/admin/AdminPageScaffold'
import { Button } from '@/src/components/ui'
import { cn } from '@/src/lib/utils/cn'
import type {
  AdminTimeWindow,
  AnalyticsSummaryFixture,
  DashboardInsightFixture,
  DashboardInsightStatus,
} from '@/src/types/fixtures'

interface AdminInsightsDashboardProps {
  insight: DashboardInsightFixture
  insightStatus: DashboardInsightStatus
  onGenerate: () => void
  onOpenChat: () => void
  onTimeWindowChange: (window: AdminTimeWindow) => void
  summary: AnalyticsSummaryFixture
  timeWindow: AdminTimeWindow
}

const timeWindowLabels: Record<AdminTimeWindow, string> = {
  '7d': 'Last 7 days',
  '30d': 'Last 30 days',
  custom: 'Custom range',
}

const headerControlClassName = 'pb-admin-header-control pb-ui-sm'

export function AdminInsightsDashboard({
  insight,
  insightStatus,
  onGenerate,
  onOpenChat,
  onTimeWindowChange,
  summary,
  timeWindow,
}: AdminInsightsDashboardProps) {
  const generating = insightStatus === 'pending' || insightStatus === 'processing'

  return (
    <AdminPageScaffold
      actions={
        <>
          <TimeWindowMenu onChange={onTimeWindowChange} value={timeWindow} />
          <Button className={headerControlClassName} disabled={generating} onClick={onGenerate} size="sm" variant="secondary">
            {generating ? <LoaderCircle className="h-[15px] w-[15px] pb-spin" /> : <RefreshCw className="h-[15px] w-[15px]" />}
            {generating ? 'Regenerating...' : 'Regenerate'}
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
      <AISummaryCard generating={generating} insight={insight} />
      <div className="mt-3.5 grid gap-4 lg:grid-cols-[1.55fr_1fr]">
        <DashboardCard title="Common topics">
          <TopicBars items={summary.top_topics} />
        </DashboardCard>
        <DashboardCard title="Risk flags">
          <RiskFlags insight={insight} />
        </DashboardCard>
      </div>
      <DashboardCard className="mt-3.5" title="Query volume" titleAside={`${summary.query_volume} this week`}>
        <QueryVolumeChart series={summary.volume_series} />
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
              className="cursor-pointer rounded-sm px-2.5 py-2 outline-none transition focus:bg-surface-hover focus:text-fg-1"
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

function AISummaryCard({ generating, insight }: { generating: boolean; insight: DashboardInsightFixture }) {
  const [open, setOpen] = useState(false)

  return (
    <section className="rounded-lg border border-border-brand bg-[linear-gradient(180deg,rgba(255,115,0,0.06),transparent_52%),var(--surface)] p-[18px]">
      <div className="mb-3 flex items-center gap-2.5">
        <span className="inline-flex items-center gap-2 text-xs font-bold text-brand">
          <Sparkles className="h-4 w-4" />
          AI summary
        </span>
        <span className="ml-auto inline-flex items-center gap-2 text-[11.5px] text-fg-3">
          {generating ? (
            <>
              <LoaderCircle className="h-3.5 w-3.5 pb-spin text-info" />
              Generating...
            </>
          ) : (
            <>
              <span className="pb-pulse h-1.5 w-1.5 rounded-full bg-success [--pulse-color:rgba(63,182,139,0.4)]" />
              Updated {insight.generated_at} · {insight.window_label}
            </>
          )}
        </span>
      </div>
      {generating ? (
        <div className="grid gap-2.5">
          <span className="h-3.5 w-[92%] rounded-pill bg-surface-raised" />
          <span className="h-3.5 w-full rounded-pill bg-surface-raised" />
          <span className="h-3.5 w-[70%] rounded-pill bg-surface-raised" />
        </div>
      ) : (
        <>
          <p className="m-0 text-[14.5px] leading-[1.65] text-fg-1">{insight.summary}</p>
          <div className="mt-3.5 grid border-t border-border pt-3.5 md:grid-cols-3">
            {insight.kpis.map((kpi, index) => (
              <div
                className={cn('min-w-0', index > 0 && 'mt-4 border-t border-border pt-4 md:mt-0 md:border-l md:border-t-0 md:pl-6 md:pt-0')}
                key={kpi.label}
              >
                <div className="flex items-baseline gap-2">
                  <span className="font-display text-[26px] font-extrabold leading-none tracking-normal text-fg-1">{kpi.value}</span>
                  <span className="text-[12.5px] font-semibold text-fg-2">{kpi.label}</span>
                </div>
                <p className="mt-1.5 text-[11.5px] text-fg-4">{kpi.sub}</p>
              </div>
            ))}
          </div>
          <button
            className="mt-3 inline-flex items-center gap-1.5 text-[12.5px] font-semibold text-brand transition hover:text-brand-hover"
            onClick={() => setOpen((current) => !current)}
            type="button"
          >
            {open ? 'Hide details' : 'Show details'}
            <ChevronDown className={cn('h-[15px] w-[15px] transition', open && 'rotate-180')} />
          </button>
          {open && (
            <div className="animate-pb-fade">
              <div className="mt-4 flex flex-wrap gap-2">
                {insight.headline_cards.map((card) => (
                  <span className="inline-flex items-center gap-2 rounded-pill border border-border bg-bg-base px-3 py-1.5" key={card.title}>
                    <span className={cn('h-[7px] w-[7px] rounded-full', severityDotClass(card.severity))} />
                    <span className="text-[12.5px] font-semibold text-fg-1">{card.title}</span>
                    <span className="text-xs text-fg-3">{card.value}</span>
                  </span>
                ))}
              </div>
              <div className="mt-[18px] border-t border-border pt-4">
                <p className="mb-3 text-[11.5px] font-bold uppercase tracking-[0.06em] text-fg-3">Recommended focus</p>
                <div className="grid gap-3 md:grid-cols-2">
                  {insight.recommended_attention_areas.map((area, index) => (
                    <div className="flex items-start gap-3" key={area}>
                      <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-sm bg-brand-soft font-display text-[11px] font-extrabold text-brand">
                        {index + 1}
                      </span>
                      <p className="text-[13px] leading-normal text-fg-2">{area}</p>
                    </div>
                  ))}
                </div>
              </div>
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
    <section className={cn('rounded-lg border border-border-strong bg-surface p-[18px]', className)}>
      <div className="mb-3 flex items-baseline">
        <h2 className="pb-card-title">{title}</h2>
        {titleAside && <span className="pb-ui-xs ml-auto text-fg-3">{titleAside}</span>}
      </div>
      {children}
    </section>
  )
}

function TopicBars({ items }: { items: AnalyticsSummaryFixture['top_topics'] }) {
  const max = Math.max(...items.map((item) => item.count), 1)
  return (
    <div className="grid gap-2.5">
      {items.map((item) => (
        <div className="grid grid-cols-[92px_1fr_34px] items-center gap-3" key={item.key}>
          <span className="truncate text-[12.5px] font-medium text-fg-2">{item.label}</span>
          <span className="h-[9px] overflow-hidden rounded-pill bg-surface-raised">
            <span
              className="block h-full rounded-pill bg-orange-600"
              style={{ width: `${Math.round((item.count / max) * 100)}%` }}
            />
          </span>
          <span className="text-right text-[12.5px] text-fg-2">{item.count}</span>
        </div>
      ))}
    </div>
  )
}

function RiskFlags({ insight }: { insight: DashboardInsightFixture }) {
  return (
    <div className="grid gap-0.5">
      {insight.risk_breakdown.map((risk, index) => (
        <div
          className={cn('flex items-center gap-3 px-1 py-3.5', index < insight.risk_breakdown.length - 1 && 'border-b border-border')}
          key={risk.label}
        >
          <span className={cn('h-2 w-2 shrink-0 rounded-full', severityDotClass(risk.severity))} />
          <span className="flex-1 text-[13.5px] text-fg-1">{risk.label}</span>
          <span className={cn('text-[10.5px] font-bold uppercase tracking-[0.04em]', severityTextClass(risk.severity))}>
            {risk.severity}
          </span>
          <span className="w-8 text-right font-display text-[19px] font-extrabold text-fg-1">{risk.count}</span>
        </div>
      ))}
    </div>
  )
}

function QueryVolumeChart({ series }: { series: AnalyticsSummaryFixture['volume_series'] }) {
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
              <span className="text-[11px] font-medium text-fg-4">{point.day}</span>
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
    <span className="inline-flex items-center gap-2 text-[11.5px] text-fg-3">
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
