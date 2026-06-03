# Epic 4: Admin Analytics and Insights

## Epic Goal

Help athletic department admins understand what athletes are asking, where Playbook cannot help yet, and which NIL/compliance/recruiting topics need attention.

### US-18
As an admin
I want a query analytics dashboard
So that I can understand what athletes are asking Playbook.

> **New in Playbook MVP.** Dashboard metrics are the primary admin analytics surface.

#### Acceptance Criteria
1. Dashboard shows query volume over time.
2. Dashboard shows common question topics.
3. Dashboard shows unanswered or declined questions.
4. Dashboard shows NIL, compliance, and recruiting-risk questions.
5. Dashboard updates from stored conversation/query records.

### US-19
As an admin
I want athlete identity anonymized in analytics
So that I can review query content without exposing names by default.

> **New in Playbook MVP.** Admins can review query text, but athlete identity should be anonymized.

#### Acceptance Criteria
1. Analytics views show query text without athlete name.
2. Analytics records include stable anonymous user identifiers for aggregation.
3. Admin APIs do not return athlete names in analytics payloads.
4. Raw conversation owner identity remains protected by normal access controls.

### US-20
As an admin
I want nightly insight generation
So that recurring gaps and risks are summarized without manual work.

> **New in Playbook MVP.** Insights should run nightly and on demand.

#### Acceptance Criteria
1. A scheduled job runs query insight generation nightly.
2. The job summarizes common topics, unanswered questions, and risk categories.
3. Failed insight jobs are logged and visible to admins.
4. Generated insight records include time window, status, and generated-at timestamp.

### US-21
As an admin
I want to generate insights on demand
So that I can inspect recent query patterns whenever needed.

> **New in Playbook MVP.** Admins can run insights manually.

#### Acceptance Criteria
1. Admins can trigger insight generation from the dashboard.
2. The request accepts a bounded time window.
3. The dashboard shows pending, processing, completed, and failed states.
4. Completed insight output is persisted and viewable later.

### US-22
As an admin
I want a talk-to-your-data side panel
So that I can ask natural-language questions about query analytics.

> **New in Playbook MVP.** TTYD-style side panel opens from a dashboard button.

#### Acceptance Criteria
1. The dashboard includes a button to open the insights side panel.
2. Admins can ask natural-language questions about analytics and insight data.
3. The side-panel agent only uses authorized analytics data.
4. The side-panel response cites or references the underlying metric or insight record when possible.
5. The side panel can be closed without losing dashboard state.

### US-23
As an admin
I want to review unanswered and risky questions
So that I can identify gaps in athlete support.

> **New in Playbook MVP.** Focus is on user questions and queries, not document drafting.

#### Acceptance Criteria
1. Dashboard lists unanswered/declined questions.
2. Dashboard lists NIL, compliance, and recruiting-risk questions.
3. Admins can filter by date range and risk/topic type.
4. Admins can open a query detail view without seeing athlete name.
5. Admin insights summarize response gaps rather than editing documents automatically.

## Edge Cases

| Edge Case | Expected Behavior |
|-----------|-------------------|
| Nightly insight job fails | Failure is visible to admins and logged |
| Dashboard has no data yet | Empty state renders without fake metrics |
| Admin asks side-panel question outside analytics scope | Agent declines and explains supported scope |
| Query includes identifying text | Owner identity remains anonymized in dashboard payload |
