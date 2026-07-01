export type AdminTimeWindow = '7d' | '30d' | 'custom'

export type DashboardInsightRunStatus = 'pending' | 'processing' | 'completed' | 'failed'

export type DashboardInsightTriggerType = 'nightly' | 'manual'

export interface AnalyticsLabelCount {
  label: string
  count: number
}

export interface AdminAnalyticsSummary {
  window_start: string
  window_end: string
  query_volume: number
  top_topics: AnalyticsLabelCount[]
  unanswered_count: number
  risk_counts: Record<string, number>
}

export interface AdminAnalyticsQuery {
  message_id: string
  anonymous_user_key: string
  text: string
  created_at: string
  topic_labels: string[]
  risk_labels: string[]
  response_status: string | null
  answer_type: string | null
  unanswered_reason: string | null
}

export interface AdminAnalyticsQueryList {
  window_start: string
  window_end: string
  queries: AdminAnalyticsQuery[]
}

export interface DashboardInsightHeadlineCard {
  title: string
  value: string
  severity?: 'low' | 'medium' | 'high'
  note?: string
}

export interface DashboardInsight {
  id: string
  run_id: string
  summary: string
  headline_cards: DashboardInsightHeadlineCard[]
  topic_breakdown: Array<Record<string, unknown>>
  unanswered_questions: Array<Record<string, unknown>>
  risk_breakdown: Array<Record<string, unknown>>
  recommended_attention_areas: string[]
  source_message_ids: string[]
  generated_at: string
}

export interface DashboardInsightRunStart {
  run_id: string
  status: DashboardInsightRunStatus
}

export interface DashboardInsightRun {
  id: string
  organization_id: string
  requested_by: string | null
  trigger_type: DashboardInsightTriggerType
  status: DashboardInsightRunStatus
  window_start: string
  window_end: string
  source_filters: Record<string, unknown>
  error_message: string | null
  created_at: string
  updated_at: string
  output: DashboardInsight | null
}

export interface DashboardInsightRunCreateRequest {
  window_start: string
  window_end: string
  source_filters?: Record<string, unknown>
}

export interface AdminAnalyticsWindowParams {
  window?: Exclude<AdminTimeWindow, 'custom'>
  window_start?: string
  window_end?: string
}
