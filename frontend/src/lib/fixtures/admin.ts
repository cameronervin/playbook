import type { AnalyticsSummaryFixture, DashboardInsightFixture } from '@/src/types/fixtures'

export const ANALYTICS_SUMMARY: AnalyticsSummaryFixture = {
  query_volume: 128,
  unanswered_count: 12,
  grounded_rate: 0.86,
  top_topics: [
    { label: 'NIL', count: 48 },
    { label: 'Compliance', count: 31 },
    { label: 'Recruiting', count: 18 },
    { label: 'Travel', count: 14 },
  ],
}

export const DASHBOARD_INSIGHT: DashboardInsightFixture = {
  generated_at: 'Fixture mode',
  summary:
    'NIL disclosure timing is the clearest support gap this week. Athletes repeatedly ask when in-kind benefits and sponsored posts must be reported.',
  recommended_attention_areas: [
    'Clarify NIL disclosure timing for in-kind benefits.',
    'Add current guidance for NIL agency-registration deadlines.',
    'Re-upload failed recruiting guidance before release.',
  ],
}
