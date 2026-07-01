import type {
  AdminAnalyticsQuery,
  AdminAnalyticsSummary,
  DashboardInsight,
  DashboardInsightHeadlineCard,
} from '@/src/types/adminAnalytics'

export interface DashboardInsightKpi {
  label: string
  value: string
  sub: string
}

export interface DashboardRiskItem {
  label: string
  count: number
  severity: 'low' | 'medium' | 'high'
}

export interface DashboardTopicItem {
  label: string
  key: string
  count: number
}

export interface DashboardVolumePoint {
  day: string
  date: string
  total: number
  unanswered: number
}

export interface DashboardUnansweredItem {
  id: string
  text: string
  reason: string
}

const SHORT_DATE_FORMATTER = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: 'numeric',
})

const GENERATED_DATE_FORMATTER = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: 'numeric',
  year: 'numeric',
})

export function dashboardKpis(
  summary: AdminAnalyticsSummary | null,
): DashboardInsightKpi[] {
  const topTopic = summary?.top_topics[0]
  const topRisk = highestRisk(summary)
  return [
    {
      label: topTopic ? `${formatLabel(topTopic.label)} questions` : 'Top topic',
      value: topTopic ? String(topTopic.count) : '0',
      sub: summary ? `${percentage(topTopic?.count ?? 0, summary.query_volume)} of all volume` : 'No query data',
    },
    {
      label: 'Unanswered',
      value: String(summary?.unanswered_count ?? 0),
      sub: summary ? `${percentage(summary.unanswered_count, summary.query_volume)} of all volume` : 'No query data',
    },
    {
      label: topRisk ? `${formatLabel(topRisk.label)} flags` : 'Risk flags',
      value: topRisk ? String(topRisk.count) : '0',
      sub: topRisk ? `${topRisk.severity} priority` : 'No risk labels',
    },
  ]
}

export function dashboardTopics(
  summary: AdminAnalyticsSummary | null,
): DashboardTopicItem[] {
  return (summary?.top_topics ?? []).map((topic) => ({
    label: formatLabel(topic.label),
    key: topic.label,
    count: topic.count,
  }))
}

export function dashboardRiskItems(
  summary: AdminAnalyticsSummary | null,
  insight: DashboardInsight | null,
): DashboardRiskItem[] {
  const riskCounts = new Map<string, number>()
  Object.entries(summary?.risk_counts ?? {}).forEach(([label, count]) => {
    riskCounts.set(label, count)
  })
  insight?.risk_breakdown.forEach((item) => {
    const label = stringField(item, 'label')
    const count = numberField(item, 'count')
    if (label && count !== null) riskCounts.set(label, count)
  })
  return [...riskCounts.entries()]
    .sort((first, second) => second[1] - first[1] || first[0].localeCompare(second[0]))
    .map(([label, count]) => ({
      label: formatLabel(label),
      count,
      severity: riskSeverity(label, count),
    }))
}

export function dashboardVolumeSeries(
  summary: AdminAnalyticsSummary | null,
  queries: AdminAnalyticsQuery[],
): DashboardVolumePoint[] {
  if (!summary) return []
  const start = new Date(summary.window_start)
  const end = new Date(summary.window_end)
  const points: DashboardVolumePoint[] = []
  const cursor = new Date(Date.UTC(start.getUTCFullYear(), start.getUTCMonth(), start.getUTCDate()))
  const endDay = new Date(Date.UTC(end.getUTCFullYear(), end.getUTCMonth(), end.getUTCDate()))
  const countsByDay = countQueriesByDay(queries)
  while (cursor <= endDay && points.length < 31) {
    const key = dateKey(cursor)
    const counts = countsByDay.get(key)
    points.push({
      day: cursor.toLocaleDateString('en-US', { weekday: 'short' }),
      date: SHORT_DATE_FORMATTER.format(cursor),
      total: counts?.total ?? 0,
      unanswered: counts?.unanswered ?? 0,
    })
    cursor.setUTCDate(cursor.getUTCDate() + 1)
  }
  if (queries.length === 0 && summary.query_volume > 0 && points.length > 0) {
    points[points.length - 1] = {
      ...points[points.length - 1],
      total: summary.query_volume,
      unanswered: summary.unanswered_count,
    }
  }
  return points
}

export function generatedLabel(insight: DashboardInsight | null): string {
  if (!insight) return 'No completed insight yet'
  return `Updated ${GENERATED_DATE_FORMATTER.format(new Date(insight.generated_at))}`
}

export function windowLabel(summary: AdminAnalyticsSummary | null): string {
  if (!summary) return 'Current window'
  return `${SHORT_DATE_FORMATTER.format(new Date(summary.window_start))} - ${SHORT_DATE_FORMATTER.format(
    new Date(summary.window_end),
  )}`
}

export function unansweredItems(insight: DashboardInsight | null): DashboardUnansweredItem[] {
  return (insight?.unanswered_questions ?? []).map((item, index) => ({
    id: stringField(item, 'message_id') || `unanswered-${index}`,
    text: stringField(item, 'text') || 'Unanswered query',
    reason: stringField(item, 'reason') || 'needs_review',
  }))
}

export function headlineCards(
  insight: DashboardInsight | null,
): DashboardInsightHeadlineCard[] {
  return (insight?.headline_cards ?? []).map((card) => ({
    title: card.title,
    value: card.value,
    severity: card.severity ?? 'medium',
    note: card.note,
  }))
}

function countQueriesByDay(
  queries: AdminAnalyticsQuery[],
): Map<string, { total: number; unanswered: number }> {
  const counts = new Map<string, { total: number; unanswered: number }>()
  queries.forEach((query) => {
    const key = dateKey(new Date(query.created_at))
    const current = counts.get(key) ?? { total: 0, unanswered: 0 }
    current.total += 1
    if (query.unanswered_reason) current.unanswered += 1
    counts.set(key, current)
  })
  return counts
}

function highestRisk(summary: AdminAnalyticsSummary | null): DashboardRiskItem | null {
  const risk = dashboardRiskItems(summary, null)[0]
  return risk ?? null
}

function dateKey(date: Date): string {
  return date.toISOString().slice(0, 10)
}

function percentage(value: number, total: number): string {
  if (total <= 0) return '0%'
  return `${Math.round((value / total) * 100)}%`
}

function riskSeverity(label: string, count: number): 'low' | 'medium' | 'high' {
  const normalized = label.toLowerCase()
  if (normalized.includes('recruiting') || count >= 5) return 'high'
  if (normalized.includes('compliance') || normalized.includes('nil') || count >= 2) return 'medium'
  return 'low'
}

function formatLabel(value: string): string {
  return value
    .replace(/[-_]+/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function stringField(item: Record<string, unknown>, key: string): string | null {
  const value = item[key]
  return typeof value === 'string' && value.trim() ? value : null
}

function numberField(item: Record<string, unknown>, key: string): number | null {
  const value = item[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}
