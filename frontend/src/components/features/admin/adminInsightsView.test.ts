import { describe, expect, it } from 'vitest'
import {
  dashboardVolumeSeries,
  dashboardRiskItems,
  headlineCards,
  queryReviewFilterOptions,
  unansweredItems,
} from '@/src/components/features/admin/adminInsightsView'
import type {
  AdminAnalyticsSummary,
  DashboardInsight,
} from '@/src/types/adminAnalytics'

const summary: AdminAnalyticsSummary = {
  window_start: '2026-06-01T00:00:00Z',
  window_end: '2026-06-08T00:00:00Z',
  query_volume: 3,
  top_topics: [
    { label: 'nil', count: 2 },
    { label: 'compliance', count: 1 },
  ],
  unanswered_count: 1,
  risk_counts: {
    compliance: 2,
  },
  volume_series: [
    { date: '2026-06-01', total: 0, unanswered: 0 },
    { date: '2026-06-02', total: 2, unanswered: 0 },
    { date: '2026-06-03', total: 1, unanswered: 1 },
  ],
}

describe('adminInsightsView', () => {
  it('builds query-review filters from summary and active filters', () => {
    expect(queryReviewFilterOptions(summary, {
      topic_labels: ['recruiting'],
      risk_labels: ['recruiting'],
    })).toEqual({
      topics: [
        { key: 'nil', label: 'Nil', count: 2 },
        { key: 'compliance', label: 'Compliance', count: 1 },
        { key: 'recruiting', label: 'Recruiting', count: 0 },
      ],
      risks: [
        { key: 'compliance', label: 'Compliance', count: 2 },
        { key: 'recruiting', label: 'Recruiting', count: 0 },
      ],
    })
  })

  it('builds query volume from summary aggregate buckets', () => {
    expect(dashboardVolumeSeries(summary)).toEqual([
      {
        key: '2026-06-01',
        day: 'Mon',
        date: 'Jun 1',
        total: 0,
        unanswered: 0,
      },
      {
        key: '2026-06-02',
        day: 'Tue',
        date: 'Jun 2',
        total: 2,
        unanswered: 0,
      },
      {
        key: '2026-06-03',
        day: 'Wed',
        date: 'Jun 3',
        total: 1,
        unanswered: 1,
      },
    ])
  })

  it('defensively ignores malformed dashboard insight breakdown rows', () => {
    const malformedInsight = {
      risk_breakdown: [
        { label: 'recruiting', count: 3 },
        null,
        'bad-row',
        { label: 'nil', count: 'many' },
      ],
      unanswered_questions: [
        { message_id: 'message-2', text: 'Can recruiting staff text this prospect?', reason: 'unsupported' },
        null,
        { text: '' },
      ],
      headline_cards: [
        { title: 'NIL disclosure timing', value: '18 questions', severity: 'medium' },
        { title: '', value: 'Missing title' },
        null,
      ],
    } as unknown as DashboardInsight

    expect(dashboardRiskItems(summary, malformedInsight).map((risk) => risk.label)).toEqual([
      'Recruiting',
      'Compliance',
    ])
    expect(unansweredItems(malformedInsight)).toEqual([
      {
        id: 'message-2',
        text: 'Can recruiting staff text this prospect?',
        reason: 'unsupported',
      },
      {
        id: 'unanswered-1',
        text: 'Unanswered query',
        reason: 'needs_review',
      },
    ])
    expect(headlineCards(malformedInsight)).toEqual([
      {
        title: 'NIL disclosure timing',
        value: '18 questions',
        severity: 'medium',
        note: undefined,
      },
    ])
  })
})
