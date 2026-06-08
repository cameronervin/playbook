import type {
  AdminChatMessageFixture,
  AdminChatReferenceFixture,
  AnalyticsSummaryFixture,
  DashboardInsightFixture,
} from '@/src/types/fixtures'

export const ANALYTICS_SUMMARY: AnalyticsSummaryFixture = {
  window_start: '2026-05-27',
  window_end: '2026-06-03',
  window_label: 'May 27 - Jun 3',
  query_volume: 128,
  query_delta: 18,
  unanswered_count: 12,
  unanswered_delta: 4,
  grounded_rate: 0.86,
  grounded_delta: -0.03,
  volume_series: [
    { day: 'Wed', date: 'May 27', total: 14, unanswered: 1 },
    { day: 'Thu', date: 'May 28', total: 19, unanswered: 2 },
    { day: 'Fri', date: 'May 29', total: 22, unanswered: 1 },
    { day: 'Sat', date: 'May 30', total: 12, unanswered: 0 },
    { day: 'Sun', date: 'May 31', total: 16, unanswered: 2 },
    { day: 'Mon', date: 'Jun 1', total: 27, unanswered: 3 },
    { day: 'Tue', date: 'Jun 2', total: 18, unanswered: 3 },
  ],
  top_topics: [
    { label: 'NIL', key: 'nil', count: 48 },
    { label: 'Compliance', key: 'compliance', count: 31 },
    { label: 'Recruiting', key: 'recruiting', count: 18 },
    { label: 'Travel', key: 'travel', count: 14 },
    { label: 'Academics', key: 'academics', count: 9 },
    { label: 'Other', key: 'other', count: 8 },
  ],
  risk_counts: { nil: 22, compliance: 14, recruiting: 3 },
}

export const DASHBOARD_INSIGHT: DashboardInsightFixture = {
  run_id: 'run_7c41a9',
  status: 'completed',
  generated_at: 'Jun 3 · 12:00 AM',
  window_label: 'May 27 - Jun 3 (7 days)',
  summary:
    'NIL disclosure timing is the clearest support gap this week. Athletes repeatedly asked when in-kind benefits - loaned vehicles, free meals, sponsored posts using school marks - must be reported, and several declined questions point to confusion between Playbook’s scope and decisions that belong to the compliance office.',
  kpis: [
    { label: 'NIL questions', value: '48', sub: '38% of all volume' },
    { label: 'Unanswered', value: '12', sub: '+4 vs last week' },
    { label: 'High-risk flags', value: '6', sub: 'recruiting contact' },
  ],
  headline_cards: [
    {
      title: 'NIL disclosure timing',
      value: '18 questions',
      severity: 'medium',
      note: 'Athletes unsure of the 72-hour window for in-kind benefits.',
    },
    {
      title: 'Recruiting-contact rules',
      value: '6 high-risk questions',
      severity: 'high',
      note: 'Prospect visits and collective contact near a dead period.',
    },
    {
      title: 'Content gap: agency deadlines',
      value: '5 unanswered',
      severity: 'high',
      note: 'No document covers NIL agency-registration deadlines.',
    },
  ],
  risk_breakdown: [
    { label: 'NIL', count: 22, severity: 'medium' },
    { label: 'Compliance', count: 14, severity: 'medium' },
    { label: 'Recruiting-risk', count: 3, severity: 'high' },
  ],
  recommended_attention_areas: [
    'Clarify NIL disclosure timing for in-kind benefits in athlete-facing guidance.',
    'Add a short document on permissible recruiting contact during dead periods.',
    'Publish the NIL agency-registration deadline for the upcoming year.',
    'Re-upload the failed recruiting-dead-periods document so it can support answers.',
  ],
}

export const ADMIN_CHAT_SUGGESTIONS = [
  'What are athletes most confused about this week?',
  'Which NIL questions were declined most often?',
  'Are recruiting-risk questions increasing?',
  'What support gaps should we address first?',
]

interface AdminChatReplyFixture {
  answer: string
  refs: AdminChatReferenceFixture[]
  answer_type: AdminChatMessageFixture['answer_type']
}

const ADMIN_CHAT_REPLIES: Array<{
  match: RegExp
  reply: AdminChatReplyFixture
}> = [
  {
    match: /confus|most asked|top|common/i,
    reply: {
      answer:
        'The clearest confusion this week is NIL disclosure timing - 18 questions touched on when in-kind benefits such as loaned vehicles, free meals, and sponsored posts using school marks must be reported. NIL is the single largest topic at 48 of 128 questions.',
      refs: [
        { type: 'metric', id: 'top_topics.nil' },
        { type: 'dashboard_insight', id: 'run_7c41a9' },
      ],
      answer_type: 'analytics_answer',
    },
  },
  {
    match: /declin|nil.*declin|reject/i,
    reply: {
      answer:
        'NIL accounted for the most declined questions this week. Both NIL-related declines were compensation or contract questions routed to the compliance office rather than answered by Playbook.',
      refs: [
        { type: 'query', id: 'q-9d55' },
        { type: 'query', id: 'q-9471' },
      ],
      answer_type: 'analytics_answer',
    },
  },
  {
    match: /recruit/i,
    reply: {
      answer:
        'Recruiting-risk questions are low in volume but high severity. They cluster around prospect contact near dead periods, including locker-room access before a spring game.',
      refs: [{ type: 'metric', id: 'risk_counts.recruiting' }],
      answer_type: 'analytics_answer',
    },
  },
]

export function adminChatReply(text: string): AdminChatReplyFixture {
  const hit = ADMIN_CHAT_REPLIES.find((reply) => reply.match.test(text))
  if (hit) return hit.reply
  if (/name|email|who is|identity|which athlete is/i.test(text)) {
    return {
      answer:
        'I cannot reveal athlete identities. Analytics are anonymized to stable IDs only, but I can break the numbers down by topic, risk, or outcome.',
      refs: [],
      answer_type: 'declined',
    }
  }
  if (/upload|delete|change role|promote|generate|run insight|edit/i.test(text)) {
    return {
      answer:
        'I can only read analytics and insights. Use the relevant admin section for document, role, or insight-run actions.',
      refs: [],
      answer_type: 'declined',
    }
  }
  return {
    answer:
      'Across 128 questions, NIL leads at 48, with 12 unanswered and an 86% grounded-answer rate. Ask me about a topic, risk type, or outcome and I will cite the metric behind it.',
    refs: [{ type: 'metric', id: 'analytics.summary' }],
    answer_type: 'analytics_answer',
  }
}
