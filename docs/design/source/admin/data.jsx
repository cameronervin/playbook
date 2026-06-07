/* data.jsx — Playbook admin mock data. Shapes mirror /api/v1 admin endpoints.
   Privacy rule: analytics may show query TEXT, never athlete names/emails —
   only stable anonymous IDs (e.g. "Athlete A-1042"). Cosmetic data only. */

/* ---------------- analytics summary (GET /admin/analytics/summary) ---------------- */
const ADMIN_SUMMARY = {
  window_start: '2026-05-27', window_end: '2026-06-03', window_label: 'May 27 – Jun 3',
  query_volume: 128, query_delta: +18,          // vs previous 7d
  unanswered_count: 12, unanswered_delta: +4,
  athletes_active: 47, athletes_delta: +6,
  grounded_rate: 0.86, grounded_delta: -0.03,    // share of answers with citations
  // daily volume — 7 points, sums to query_volume
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
  // outcome split across the 128 queries
  status_counts: { answered: 104, declined: 7, unsupported: 4, failed: 1, partial: 12 },
};

/* ---------------- query review (GET /admin/analytics/queries) ---------------- */
// topics, risks, statuses are label sets; status outcomes: answered|declined|unsupported|failed
const ADMIN_QUERIES = [
  { id: 'q-9f31', athlete: 'A-1042', text: 'If a local dealership gives me a truck to drive, when do I have to report that NIL deal?', when: 'Jun 2 · 4:18 PM', topics: ['NIL'], risks: ['nil'], status: 'answered', cites: 2, safety: null,
    answer: 'Any NIL benefit valued at $600 or more must be disclosed to the compliance office within 72 hours of the agreement. A loaned vehicle counts as an in-kind benefit and is valued at fair-market rate.', reason: null, refs: ['NIL_POLICY_2025.PDF', 'NCAA_BYLAW_13.PDF'] },
  { id: 'q-9e07', athlete: 'A-0883', text: 'Can my high-school cousin who is being recruited come sit in our locker room before the spring game?', when: 'Jun 2 · 1:02 PM', topics: ['Recruiting'], risks: ['recruiting', 'compliance'], status: 'answered', cites: 1, safety: null,
    answer: 'Locker-room access for a prospective student-athlete during an unofficial visit is restricted. Contact the compliance office to log the visit before granting any access.', reason: null, refs: ['NCAA_BYLAW_13.PDF'] },
  { id: 'q-9d55', athlete: 'A-1290', text: 'What happens to my NIL collective payments if I enter the transfer portal mid-season?', when: 'Jun 2 · 11:47 AM', topics: ['NIL', 'Compliance'], risks: ['nil', 'compliance'], status: 'declined', cites: 0, safety: 'out_of_scope',
    answer: null, reason: 'Question requires individualized legal/financial advice about a third-party collective contract, which is outside the knowledge base. Athlete was routed to the compliance office.', refs: [] },
  { id: 'q-9c12', athlete: 'A-0461', text: 'Whats the meal per diem for the road trip to Ames this weekend?', when: 'Jun 1 · 6:33 PM', topics: ['Travel'], risks: [], status: 'answered', cites: 2, safety: null,
    answer: 'The current meal per diem for team travel is $65/day — $15 breakfast / $20 lunch / $30 dinner. Provided team meals are deducted from the daily rate.', reason: null, refs: ['PER_DIEM_RATES.XLSX', 'TRAVEL_POLICY_2025.PDF'] },
  { id: 'q-9b88', athlete: 'A-1042', text: 'Is it allowed to post my game highlights with the school logo on a paid sponsorship reel?', when: 'Jun 1 · 3:10 PM', topics: ['NIL'], risks: ['nil'], status: 'answered', cites: 2, safety: null,
    answer: 'Deals that reference university marks, facilities, or uniforms require a brand-use review before the agreement is finalized. Submit the reel through the compliance portal first.', reason: null, refs: ['NIL_POLICY_2025.PDF'] },
  { id: 'q-9a04', athlete: 'A-0719', text: 'How do I report a teammate I think is being pressured into a bad NIL contract?', when: 'Jun 1 · 10:21 AM', topics: ['NIL', 'Compliance'], risks: ['nil', 'compliance'], status: 'answered', cites: 1, safety: 'sensitive',
    answer: 'You can report a concern confidentially to the compliance office. Playbook surfaced the reporting contact and the athlete-protection policy. No personal details are stored.', reason: null, refs: ['NIL_POLICY_2025.PDF'] },
  { id: 'q-99f1', athlete: 'A-1551', text: 'What GPA do I need to stay eligible to travel next semester?', when: 'May 31 · 8:55 PM', topics: ['Academics'], risks: [], status: 'answered', cites: 1, safety: null,
    answer: 'A 2.3 cumulative GPA is required for team travel. Below that, you can petition Academic Services with an approved study-hall plan.', reason: null, refs: ['STUDY_HALL_POLICY.PDF'] },
  { id: 'q-98ad', athlete: 'A-0461', text: 'Can a booster pay me directly to appear at their car wash fundraiser?', when: 'May 31 · 2:40 PM', topics: ['NIL', 'Compliance'], risks: ['nil', 'compliance', 'recruiting'], status: 'answered', cites: 2, safety: null,
    answer: 'A booster-arranged paid appearance is permissible only as a disclosed NIL activity at fair-market value and cannot be tied to enrollment or performance. Disclose it before agreeing.', reason: null, refs: ['NIL_POLICY_2025.PDF', 'NCAA_BYLAW_13.PDF'] },
  { id: 'q-9722', athlete: 'A-1290', text: 'where do i pick up my parking pass for the family on gameday', when: 'May 30 · 5:12 PM', topics: ['Other'], risks: [], status: 'answered', cites: 1, safety: null,
    answer: 'Family parking passes are claimed in the athlete app and picked up at the Will Call window on the west side of the stadium starting 3 hours before kickoff.', reason: null, refs: ['GAMEDAY_FAQ.PDF'] },
  { id: 'q-9610', athlete: 'A-0998', text: 'What is the deadline to add my NIL agency to the disclosure portal for next year?', when: 'May 30 · 9:30 AM', topics: ['NIL'], risks: ['nil'], status: 'unsupported', cites: 0, safety: null,
    answer: null, reason: 'No document in the knowledge base covers agency-registration deadlines for the upcoming year. Flagged as a content gap for the compliance team.', refs: [] },
  { id: 'q-9588', athlete: 'A-1551', text: 'Can I get a tutor for organic chem before finals week?', when: 'May 29 · 7:05 PM', topics: ['Academics'], risks: [], status: 'answered', cites: 1, safety: null,
    answer: 'Request a tutor through the Student Services portal at least 48 hours before your intended session. Finals-week slots fill quickly.', reason: null, refs: ['TUTORING_GUIDE.DOCX'] },
  { id: 'q-9471', athlete: 'A-0719', text: 'how much can a collective pay an incoming freshman recruit before signing day', when: 'May 29 · 12:48 PM', topics: ['Recruiting', 'NIL'], risks: ['recruiting', 'nil'], status: 'declined', cites: 0, safety: 'out_of_scope',
    answer: null, reason: 'Asks about permissible compensation for a prospect prior to enrollment — a compliance determination that must come from the compliance office, not Playbook.', refs: [] },
  { id: 'q-9360', athlete: 'A-0883', text: 'Is the indoor field open for me to get extra reps on Sunday morning?', when: 'May 28 · 4:22 PM', topics: ['Other'], risks: [], status: 'answered', cites: 1, safety: null,
    answer: 'The indoor practice field can be reserved up to 14 days ahead through the Operations portal. In-season teams hold priority; open slots release Mondays at 8:00 a.m.', reason: null, refs: ['FACILITY_HOURS.PDF'] },
  { id: 'q-9241', athlete: 'A-0998', text: 'My disclosure form keeps erroring when I upload the contract PDF — what do I do?', when: 'May 28 · 9:14 AM', topics: ['NIL', 'Other'], risks: ['nil'], status: 'failed', cites: 0, safety: null,
    answer: null, reason: 'Answer generation failed: the retrieval step timed out. The athlete was shown a fallback message and the support contact. Logged for review.', refs: [] },
  { id: 'q-9130', athlete: 'A-1042', text: 'Do I have to tell compliance about a free meal from a restaurant that wants a shoutout?', when: 'May 27 · 6:40 PM', topics: ['NIL', 'Compliance'], risks: ['nil', 'compliance'], status: 'answered', cites: 2, safety: null,
    answer: 'A free meal exchanged for a social-media post is an NIL benefit. If the total value across the arrangement reaches $600, it must be disclosed within 72 hours.', reason: null, refs: ['NIL_POLICY_2025.PDF', 'NCAA_BYLAW_13.PDF'] },
];

/* ---------------- dashboard insights (GET /admin/dashboard-insights/*) ---------------- */
const ADMIN_INSIGHT = {
  run_id: 'run_7c41a9', status: 'completed',
  generated_at: 'Jun 3 · 12:00 AM', window_label: 'May 27 – Jun 3 (7 days)',
  summary: 'NIL disclosure timing is the clearest support gap this week. Athletes repeatedly asked when in-kind benefits — loaned vehicles, free meals, sponsored posts using school marks — must be reported, and several declined questions point to confusion between Playbook\u2019s scope and decisions that belong to the compliance office.',
  // KPIs the agent surfaced as most relevant to this week's analysis
  kpis: [
    { label: 'NIL questions', value: '48', sub: '38% of all volume' },
    { label: 'Unanswered', value: '12', sub: '+4 vs last week' },
    { label: 'High-risk flags', value: '6', sub: 'recruiting contact' },
  ],
  headline_cards: [
    { title: 'NIL disclosure timing', value: '18 questions', severity: 'medium', note: 'Athletes unsure of the 72-hour window for in-kind benefits.' },
    { title: 'Recruiting-contact rules', value: '6 high-risk questions', severity: 'high', note: 'Prospect visits and collective contact near a dead period.' },
    { title: 'Content gap: agency deadlines', value: '5 unanswered', severity: 'high', note: 'No document covers NIL agency-registration deadlines.' },
  ],
  topic_breakdown: [
    { label: 'NIL', count: 48 }, { label: 'Compliance', count: 31 }, { label: 'Recruiting', count: 18 },
    { label: 'Travel', count: 14 }, { label: 'Academics', count: 9 }, { label: 'Other', count: 8 },
  ],
  unanswered_summary: '12 questions went unanswered, declined, or failed. The largest cluster (5) concerns NIL compensation amounts and agency deadlines that no current document covers.',
  risk_breakdown: [
    { label: 'NIL', count: 22, severity: 'medium' },
    { label: 'Compliance', count: 14, severity: 'medium' },
    { label: 'Recruiting-risk', count: 3, severity: 'high' },
  ],
  recommended_attention_areas: [
    'Clarify NIL disclosure timing for in-kind benefits in athlete-facing guidance.',
    'Add a short document on permissible recruiting contact during dead periods.',
    'Publish the NIL agency-registration deadline for the upcoming year (current gap).',
    'Re-upload the failed recruiting-dead-periods document so it can support answers.',
  ],
};

// run history (GET /admin/dashboard-insights/runs) — newest first
const ADMIN_INSIGHT_RUNS = [
  { id: 'run_7c41a9', status: 'completed', window_label: 'May 27 – Jun 3', trigger: 'Scheduled', when: 'Jun 3 · 12:00 AM', by: 'Nightly job' },
  { id: 'run_6b0e72', status: 'completed', window_label: 'May 20 – May 27', trigger: 'Scheduled', when: 'May 27 · 12:00 AM', by: 'Nightly job' },
  { id: 'run_6a93f1', status: 'failed', window_label: 'May 24 – May 26', trigger: 'Manual', when: 'May 26 · 2:14 PM', by: 'You', error: 'Insufficient query volume for the selected window.' },
  { id: 'run_69c200', status: 'completed', window_label: 'May 13 – May 20', trigger: 'Scheduled', when: 'May 20 · 12:00 AM', by: 'Nightly job' },
];

/* ---------------- KB documents (GET /admin/kb/documents) ---------------- */
// status: uploaded | processing | ready | failed
const ADMIN_DOCS = [
  { id: 'doc_a1', collId: 'compliance', title: 'NIL_POLICY_2025.PDF', type: 'PDF', size: '1.8 MB', status: 'ready', uploaded: 'Mar 14, 2026', uploader: 'You', tags: ['NIL', 'Compliance'], official: true, priority: 'High', source_date: 'Mar 2026', visibility: 'All athletes', reason: null },
  { id: 'doc_a2', collId: 'compliance', title: 'NCAA_BYLAW_13.PDF', type: 'PDF', size: '3.2 MB', status: 'ready', uploaded: 'Jan 9, 2026', uploader: 'M. Carter', tags: ['Recruiting', 'Compliance'], official: true, priority: 'High', source_date: 'Aug 2025', visibility: 'All athletes', reason: null },
  { id: 'doc_a3', collId: 'travel', title: 'PER_DIEM_RATES.XLSX', type: 'XLSX', size: '88 KB', status: 'ready', uploaded: 'Jun 1, 2026', uploader: 'You', tags: ['Travel'], official: true, priority: 'Normal', source_date: 'Jun 2026', visibility: 'All athletes', reason: null },
  { id: 'doc_a4', collId: 'compliance', title: 'NIL_AGENCY_GUIDE_2027.DOCX', type: 'DOCX', size: '640 KB', status: 'processing', uploaded: 'Jun 3, 2026', uploader: 'You', tags: ['NIL'], official: false, priority: 'Normal', source_date: '—', visibility: 'All athletes', reason: null },
  { id: 'doc_a5', collId: 'academics', title: 'STUDY_HALL_POLICY.PDF', type: 'PDF', size: '420 KB', status: 'ready', uploaded: 'Feb 2, 2026', uploader: 'R. Diaz', tags: ['Academics'], official: true, priority: 'Normal', source_date: 'Jan 2026', visibility: 'All athletes', reason: null },
  { id: 'doc_a6', collId: 'compliance', title: 'RECRUITING_DEAD_PERIODS.PDF', type: 'PDF', size: '1.1 MB', status: 'failed', uploaded: 'Jun 3, 2026', uploader: 'You', tags: ['Recruiting'], official: false, priority: 'High', source_date: '—', visibility: 'All athletes', reason: 'Scanned PDF — no extractable text layer. Re-upload a text-based version.' },
  { id: 'doc_a7', collId: 'donor', title: 'BOOSTER_HANDBOOK_2024.PPTX', type: 'PPTX', size: '12.4 MB', status: 'ready', uploaded: 'Nov 18, 2025', uploader: 'M. Carter', tags: ['Donor', 'Compliance'], official: false, priority: 'Low', source_date: 'Nov 2024', visibility: 'All athletes', reason: null },
  { id: 'doc_a8', collId: 'compliance', title: 'TRANSFER_PORTAL_SOP.PDF', type: 'PDF', size: '560 KB', status: 'uploaded', uploaded: 'Jun 3, 2026', uploader: 'You', tags: ['Compliance'], official: false, priority: 'Normal', source_date: 'Jan 2026', visibility: 'All athletes', reason: null },
];

/* ---------------- KB collections (how documents are divided) ---------------- */
const ADMIN_KB_COLLECTIONS = [
  { id: 'compliance', name: 'Compliance & NIL', icon: 'shield', blurb: 'NIL, eligibility, and recruiting rules — kept current with OSU and NCAA policy.' },
  { id: 'travel', name: 'Team Travel', icon: 'plane', blurb: 'Per-diem rates, charter logistics, and team hotel policy for every sport.' },
  { id: 'academics', name: 'Academic Services', icon: 'book-open', blurb: 'Study-hall rules, tutoring, and academic eligibility support.' },
  { id: 'donor', name: 'Donor Relations', icon: 'users', blurb: 'Giving levels, suite benefits, and Cowboy Club answers for boosters.' },
];

/* ---------------- users (super-admin only) ---------------- */
const ADMIN_USERS = [
  { id: 'u1', name: 'Jordan Mitchell', email: 'j.mitchell@okstate.edu', role: 'super_admin', last_active: 'Active now', you: true },
  { id: 'u2', name: 'Maya Carter', email: 'm.carter@okstate.edu', role: 'admin', last_active: '2h ago' },
  { id: 'u3', name: 'Ray Diaz', email: 'r.diaz@okstate.edu', role: 'admin', last_active: 'Yesterday' },
  { id: 'u4', name: 'Tom Becker', email: 't.becker@okstate.edu', role: 'athlete', last_active: '4d ago' },
  { id: 'u5', name: 'Priya Shah', email: 'p.shah@okstate.edu', role: 'athlete', last_active: '1d ago' },
  { id: 'u6', name: 'Dana Lowe', email: 'd.lowe@okstate.edu', role: 'admin', last_active: '3d ago' },
];

/* ---------------- audit log (super-admin only, immutable) ---------------- */
const ADMIN_AUDIT = [
  { id: 'ev_01', actor: 'You', action: 'insight.trigger', label: 'Triggered dashboard insight', target_type: 'insight_run', target_id: 'run_6a93f1', when: 'Jun 3 · 2:14 PM', meta: 'window: May 24 – May 26' },
  { id: 'ev_02', actor: 'You', action: 'kb.upload', label: 'Uploaded KB document', target_type: 'document', target_id: 'doc_a8', when: 'Jun 3 · 1:55 PM', meta: 'TRANSFER_PORTAL_SOP.PDF' },
  { id: 'ev_03', actor: 'You', action: 'kb.upload', label: 'Uploaded KB document', target_type: 'document', target_id: 'doc_a6', when: 'Jun 3 · 1:40 PM', meta: 'RECRUITING_DEAD_PERIODS.PDF · failed processing' },
  { id: 'ev_04', actor: 'M. Carter', action: 'role.change', label: 'Promoted user to admin', target_type: 'user', target_id: 'u6', when: 'Jun 2 · 9:12 AM', meta: 'd.lowe@okstate.edu · athlete → admin' },
  { id: 'ev_05', actor: 'You', action: 'kb.metadata', label: 'Updated document metadata', target_type: 'document', target_id: 'doc_a3', when: 'Jun 1 · 4:03 PM', meta: 'PER_DIEM_RATES.XLSX · priority: Normal, official: true' },
  { id: 'ev_06', actor: 'R. Diaz', action: 'kb.delete', label: 'Archived KB document', target_type: 'document', target_id: 'doc_x9', when: 'May 30 · 11:20 AM', meta: 'TICKET_TRANSFER_GUIDE_OLD.PDF' },
  { id: 'ev_07', actor: 'M. Carter', action: 'kb.retry', label: 'Retried failed document', target_type: 'document', target_id: 'doc_a2', when: 'Jan 9 · 10:02 AM', meta: 'NCAA_BYLAW_13.PDF' },
];

/* ---------------- admin analytics chat — canned replies ---------------- */
// references: { type: metric|dashboard_insight|query, id }
const ADMIN_CHAT_SUGGESTIONS = [
  'What are athletes most confused about this week?',
  'Which NIL questions were declined most often?',
  'Are recruiting-risk questions increasing?',
  'What support gaps should we address first?',
];
const ADMIN_CHAT_REPLIES = [
  { match: /confus|most asked|top|common/i,
    answer: 'The clearest confusion this week is NIL disclosure timing — 18 questions touched on when in-kind benefits (loaned vehicles, free meals, sponsored posts using school marks) must be reported. NIL is the single largest topic at 48 of 128 questions.',
    refs: [{ type: 'metric', id: 'top_topics.nil' }, { type: 'dashboard_insight', id: 'run_7c41a9' }] },
  { match: /declin|nil.*declin|reject/i,
    answer: 'NIL accounted for the most declined questions this week. Both NIL-related declines were compensation/contract questions — how much a collective can pay, and what happens to collective payments in the portal — which are routed to the compliance office rather than answered by Playbook.',
    refs: [{ type: 'query', id: 'q-9d55' }, { type: 'query', id: 'q-9471' }, { type: 'metric', id: 'status_counts.declined' }] },
  { match: /recruit/i,
    answer: 'Recruiting-risk questions are low in volume (3) but flagged high-severity. They cluster around prospect contact near dead periods — for example a recruit visiting the locker room before the spring game. Volume is flat week-over-week, not rising.',
    refs: [{ type: 'metric', id: 'risk_counts.recruiting' }, { type: 'query', id: 'q-9e07' }] },
  { match: /gap|address|fix|priorit|improve/i,
    answer: 'Top support gap to address first: NIL disclosure timing for in-kind benefits — it is the largest confusion cluster and is fully within your control to clarify. Second, there is a genuine content gap: no document covers NIL agency-registration deadlines for the upcoming year, which caused an unsupported answer.',
    refs: [{ type: 'dashboard_insight', id: 'run_7c41a9' }, { type: 'query', id: 'q-9610' }] },
];
const adminChatReply = (text) => {
  const hit = ADMIN_CHAT_REPLIES.find(r => r.match.test(text));
  if (hit) return { answer: hit.answer, refs: hit.refs, answer_type: 'analytics_answer' };
  if (/name|email|who is|identity|which athlete is/i.test(text)) {
    return { answer: 'I can\u2019t reveal athlete identities — analytics are anonymized to stable IDs only (e.g. Athlete A-1042). I can break the numbers down by topic, risk, or outcome instead.', refs: [], answer_type: 'declined' };
  }
  if (/upload|delete|change role|promote|generate|run insight|edit/i.test(text)) {
    return { answer: 'I can only read analytics and insights — I can\u2019t take actions like uploading documents, changing roles, or triggering insight runs. Use the relevant admin section for that.', refs: [], answer_type: 'declined' };
  }
  return { answer: 'Here\u2019s what the analytics show for this window. Across 128 questions, NIL leads at 48, with 12 unanswered and an 86% grounded-answer rate. Ask me about a topic, risk type, or outcome and I\u2019ll cite the metric or query behind it.', refs: [{ type: 'metric', id: 'analytics.summary' }], answer_type: 'analytics_answer' };
};

Object.assign(window, {
  ADMIN_SUMMARY, ADMIN_QUERIES, ADMIN_INSIGHT, ADMIN_INSIGHT_RUNS, ADMIN_DOCS, ADMIN_KB_COLLECTIONS,
  ADMIN_USERS, ADMIN_AUDIT, ADMIN_CHAT_SUGGESTIONS, adminChatReply,
});
