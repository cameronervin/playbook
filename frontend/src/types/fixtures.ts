export interface AnalyticsSummaryFixture {
  query_volume: number
  unanswered_count: number
  grounded_rate: number
  top_topics: Array<{ label: string; count: number }>
}

export interface DashboardInsightFixture {
  summary: string
  generated_at: string
  recommended_attention_areas: string[]
}

export interface AdminChatMessageFixture {
  id: string
  role: 'user' | 'assistant'
  content: string
}
