import type {
  AdminAnalyticsQueryFilters,
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
  key: string
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

export interface QueryReviewFilterOption {
  key: string
  label: string
  count: number
}

export interface QueryReviewFilterOptions {
  topics: QueryReviewFilterOption[]
  risks: QueryReviewFilterOption[]
}

const SHORT_DATE_FORMATTER = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: 'numeric',
  timeZone: 'UTC',
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
  recordList(insight?.risk_breakdown).forEach((item) => {
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
): DashboardVolumePoint[] {
  if (!summary) return []
  return summary.volume_series.map((point) => {
    const date = new Date(`${point.date}T00:00:00Z`)
    return {
      key: point.date,
      day: date.toLocaleDateString('en-US', { weekday: 'short', timeZone: 'UTC' }),
      date: SHORT_DATE_FORMATTER.format(date),
      total: point.total,
      unanswered: point.unanswered,
    }
  })
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
  return (insight?.unanswered_questions ?? []).flatMap((item, index) => {
    const record = recordField(item)
    if (!record) {
      return [{
        id: `unanswered-${index}`,
        text: 'Unanswered query',
        reason: 'needs_review',
      }]
    }
    const text = stringField(record, 'text')
    const reason = stringField(record, 'reason')
    const id = stringField(record, 'message_id')
    if (!text && !reason && !id) return []
    return [{
      id: id || `unanswered-${index}`,
      text: text || 'Unanswered query',
      reason: reason || 'needs_review',
    }]
  })
}

export function headlineCards(
  insight: DashboardInsight | null,
): DashboardInsightHeadlineCard[] {
  return recordList(insight?.headline_cards).flatMap((card) => {
    const title = stringField(card, 'title')
    const value = stringField(card, 'value')
    if (!title || !value) return []
    return [{
      title,
      value,
      severity: severityField(card, 'severity') ?? 'medium',
      note: stringField(card, 'note') ?? undefined,
    }]
  })
}

export function queryReviewFilterOptions(
  summary: AdminAnalyticsSummary | null,
  filters: AdminAnalyticsQueryFilters,
): QueryReviewFilterOptions {
  const topicCounts = new Map<string, number>()
  const riskCounts = new Map<string, number>()
  summary?.top_topics.forEach((topic) => {
    topicCounts.set(topic.label, topic.count)
  })
  Object.entries(summary?.risk_counts ?? {}).forEach(([label, count]) => {
    riskCounts.set(label, count)
  })
  filters.topic_labels?.forEach((label) => seedMissingLabel(topicCounts, label))
  filters.risk_labels?.forEach((label) => seedMissingLabel(riskCounts, label))
  return {
    topics: mapFilterOptions(topicCounts),
    risks: mapFilterOptions(riskCounts),
  }
}

function highestRisk(summary: AdminAnalyticsSummary | null): DashboardRiskItem | null {
  const risk = dashboardRiskItems(summary, null)[0]
  return risk ?? null
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

function recordList(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value)
    ? value.flatMap((item) => {
        const record = recordField(item)
        return record ? [record] : []
      })
    : []
}

function recordField(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null
}

function stringField(item: Record<string, unknown>, key: string): string | null {
  const value = item[key]
  return typeof value === 'string' && value.trim() ? value : null
}

function numberField(item: Record<string, unknown>, key: string): number | null {
  const value = item[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function severityField(
  item: Record<string, unknown>,
  key: string,
): DashboardInsightHeadlineCard['severity'] | null {
  const value = item[key]
  return value === 'low' || value === 'medium' || value === 'high' ? value : null
}

function seedMissingLabel(
  counts: Map<string, number>,
  label: string,
): void {
  const key = label.trim()
  if (!key || counts.has(key)) return
  counts.set(key, 0)
}

function mapFilterOptions(counts: Map<string, number>): QueryReviewFilterOption[] {
  return [...counts.entries()]
    .sort((first, second) => second[1] - first[1] || first[0].localeCompare(second[0]))
    .map(([key, count]) => ({
      key,
      label: formatLabel(key),
      count,
    }))
}
