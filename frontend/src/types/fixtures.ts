export type AdminTimeWindow = '7d' | '30d' | 'custom'

export type DashboardInsightStatus = 'pending' | 'processing' | 'completed' | 'failed'

export interface AnalyticsTopicFixture {
  label: string
  key: string
  count: number
}

export interface VolumeSeriesPointFixture {
  day: string
  date: string
  total: number
  unanswered: number
}

export interface AnalyticsSummaryFixture {
  window_start: string
  window_end: string
  window_label: string
  query_volume: number
  query_delta: number
  unanswered_count: number
  unanswered_delta: number
  grounded_rate: number
  grounded_delta: number
  volume_series: VolumeSeriesPointFixture[]
  top_topics: AnalyticsTopicFixture[]
  risk_counts: {
    nil: number
    compliance: number
    recruiting: number
  }
}

export interface DashboardInsightKpiFixture {
  label: string
  value: string
  sub: string
}

export interface DashboardInsightHeadlineFixture {
  title: string
  value: string
  severity: 'low' | 'medium' | 'high'
  note: string
}

export interface DashboardRiskBreakdownFixture {
  label: string
  count: number
  severity: 'low' | 'medium' | 'high'
}

export interface DashboardInsightFixture {
  run_id: string
  status: DashboardInsightStatus
  summary: string
  generated_at: string
  window_label: string
  kpis: DashboardInsightKpiFixture[]
  headline_cards: DashboardInsightHeadlineFixture[]
  risk_breakdown: DashboardRiskBreakdownFixture[]
  recommended_attention_areas: string[]
}
