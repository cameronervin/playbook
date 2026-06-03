# Playbook Master User Stories

This file consolidates Playbook MVP scope across five epics:
1. Authentication, roles, and seamless entry
2. Athlete AI chat experience
3. Knowledge base and document operations
4. Admin analytics and insights
5. Safety, governance, and release readiness

Story numbering is contiguous across all active stories.

## Epic 1: Authentication, Roles, and Seamless Entry

### US-01
As an athlete
I want to sign in with Google or Microsoft
So that I can access Playbook without creating another password.

> **New in Playbook MVP.** Requested by product owner for a low-friction prototype.

#### Acceptance Criteria
1. A user can start Google OAuth/OIDC sign-in from the login screen.
2. A user can start Microsoft OAuth/OIDC sign-in from the login screen.
3. Successful sign-in creates or updates a local user record with email, name, provider, and provider subject.
4. Failed sign-in returns a clear error without creating a partial session.
5. No paid third-party auth vendor is required for the MVP implementation.

### US-02
As a new athlete
I want to self-register and land directly in chat
So that I can ask a question without onboarding friction.

> **New in Playbook MVP.** Day-one success depends on a seamless first experience.

#### Acceptance Criteria
1. A first-time authenticated user can select the athlete role during signup.
2. The signup flow collects name, email, and sport/team.
3. After profile creation, the athlete lands directly on the chat screen.
4. Returning athletes skip signup and land directly on the chat screen.
5. Missing required profile fields block entry with inline validation.

### US-03
As a super admin
I want to promote signed-in users into admin roles
So that athletic department operators can manage Playbook without a separate login system.

> **New in Playbook MVP.** Admin users also sign in through Google/Microsoft and are promoted by a super admin.

#### Acceptance Criteria
1. A super admin can view registered users.
2. A super admin can assign `admin` or `super_admin` roles.
3. Role changes take effect on the user's next authorized request or session refresh.
4. Role changes are recorded in the audit log with actor, target user, previous role, new role, and timestamp.
5. The role model supports future role values without schema redesign.

### US-04
As an admin
I want role-based access controls
So that athlete, admin, and super-admin capabilities remain separated.

> **New in Playbook MVP.** Role-based answer and admin access are critical.

#### Acceptance Criteria
1. Athletes cannot access admin routes or admin API endpoints.
2. Admins can manage documents and view analytics but cannot promote super admins unless granted that role.
3. Super admins can manage users and roles.
4. Unauthorized API access returns 403 with a structured error.
5. Route guards and API authorization are covered by automated tests.

## Epic 2: Athlete AI Chat Experience

### US-05
As an athlete
I want a chat-first home screen
So that I can immediately ask Playbook for help.

> **New in Playbook MVP.** The primary athlete experience is a simple chat surface.

#### Acceptance Criteria
1. The authenticated athlete home route renders a chat input as the primary focus.
2. The screen includes a conversation history sidebar.
3. The screen includes an upload button.
4. The screen remains usable on standard desktop and responsive web viewports.
5. Empty state content does not imply affiliation with any specific university.

### US-06
As an athlete
I want to ask NIL, compliance, and process questions
So that I can get quick guidance from athletic department knowledge.

> **New in Playbook MVP.** Initial questions include "How do I do X?", "Can I do Y?", and "Where do I upload Z?"

#### Acceptance Criteria
1. The athlete can submit a natural-language question.
2. The backend creates a conversation message record before generation starts.
3. The answer is generated through the Playbook chat agent.
4. The answer uses available knowledgebase context for policy and process guidance.
5. The answer is direct, concise, and warm.
6. The final response is saved to conversation history.

### US-07
As an athlete
I want answers to stream as they are generated
So that Playbook feels responsive while the agent works.

> **New in Playbook MVP.** Streaming is required for perceived quality.

#### Acceptance Criteria
1. Chat generation emits incremental response chunks to the frontend.
2. The UI renders streamed text without blocking the input shell.
3. If streaming fails, the conversation displays a recoverable error state.
4. Completed streamed output is persisted as the final assistant message.

### US-08
As an athlete
I want answers to include source citations
So that I can see which department documents support the answer.

> **New in Playbook MVP.** Citations should appear at the bottom of answers.

#### Acceptance Criteria
1. Every grounded answer includes citations at the bottom.
2. Each citation shows the source document title.
3. Citation metadata links the answer to retrieved chunks or document records.
4. If no source supports a policy/process answer, the agent declines instead of fabricating a citation.
5. Citation rendering remains readable in conversation history.

### US-09
As an athlete
I want to upload supported files into a chat
So that Playbook can consider my document or screenshot-like material in that conversation.

> **New in Playbook MVP.** Athlete uploads are conversation-scoped, not shared KB documents.

#### Acceptance Criteria
1. The chat upload control accepts supported document types: PDF, DOCX, PPTX, and XLSX.
2. Uploaded files are attached to the active conversation.
3. Uploaded file content can be used for that conversation's answer context.
4. Uploaded files are retained and visible in conversation history.
5. Athlete-uploaded files are not added to the shared knowledgebase.

### US-10
As an athlete
I want to see my full conversation history
So that I can return to previous Playbook answers.

> **New in Playbook MVP.** Full history is required for the prototype.

#### Acceptance Criteria
1. The history sidebar lists prior conversations for the signed-in athlete.
2. Selecting a conversation loads messages, citations, and retained file attachments.
3. Athletes can only view their own conversations.
4. New messages append to the selected conversation.
5. History retrieval is paginated or otherwise bounded to avoid slow initial loads.

### US-11
As an athlete
I want Playbook to decline questions it should not answer
So that I am not misled on sensitive or unsupported topics.

> **New in Playbook MVP.** Unknown or unsafe answers should direct athletes to the athletic department.

#### Acceptance Criteria
1. The agent declines when it lacks sufficient KB support for policy/process guidance.
2. The agent declines medical, legal, mental-health, harassment/reporting, emergency, and recruiting-risk advice outside approved guidance.
3. Declines tell the athlete to contact the athletic department.
4. Emergency-related messages refuse advice and show emergency instructions.
5. Declines are stored for admin analytics.

## Epic 3: Knowledge Base and Document Operations

### US-12
As an admin
I want to upload department documents
So that athletes can receive answers from current athletic department knowledge.

> **New in Playbook MVP.** Documents include compliance materials, manuals, handbooks, coaching content, and system process instructions.

#### Acceptance Criteria
1. Admins can upload supported KB documents.
2. Uploaded documents become eligible for processing immediately.
3. The system records uploader, filename, size, content type, and upload timestamp.
4. Failed uploads return a clear error and do not create ready documents.
5. Upload actions are recorded in the audit log.

### US-13
As an admin
I want to see document processing status
So that I know whether uploaded content is ready for athlete answers.

> **New in Playbook MVP.** Status states should include uploaded, processing, ready, and failed.

#### Acceptance Criteria
1. Uploaded documents show `uploaded` before processing starts.
2. Documents show `processing` during parse, chunk, embed, and load stages.
3. Documents show `ready` after searchable vectors are available.
4. Documents show `failed` when extraction or indexing fails.
5. Failed status includes a clear reason when available.

### US-14
As an admin
I want failed documents to be retryable
So that bad extraction or no-text failures can be corrected.

> **New in Playbook MVP.** Admins can retry or re-upload failed documents.

#### Acceptance Criteria
1. A failed document exposes retry or re-upload actions.
2. Retrying restarts the processing pipeline.
3. Re-uploading preserves audit history of the replacement action.
4. A no-text extraction failure is marked failed with a clear message.
5. Athletes do not receive answers from failed documents.

### US-15
As an admin
I want metadata tags for documents
So that retrieval can prefer official, current, and high-priority sources.

> **New in Playbook MVP.** Metadata tags are preferred over a hard category taxonomy.

#### Acceptance Criteria
1. Admins can assign metadata tags to documents.
2. Tags support official/priority/source/freshness concepts.
3. Retrieval stores and returns metadata needed for ranking and citations.
4. Official or priority metadata can influence retrieval when sources conflict.
5. Metadata changes are recorded in the audit log.

### US-16
As an admin
I want all MVP documents visible to all athletes
So that the prototype stays simple while preserving an extensible access model.

> **New in Playbook MVP.** Future access may vary by sport, team, or audience.

#### Acceptance Criteria
1. MVP KB documents are visible to all athletes by default.
2. The document model includes fields or structure that can support future audience rules.
3. Retrieval filters enforce the active visibility rule.
4. Future team/sport visibility can be added without replacing the document table.

### US-17
As an athlete
I want Playbook to use the newest source when documents conflict
So that answers reflect current department guidance.

> **New in Playbook MVP.** Newest source is the default conflict rule, with room for official/priority metadata.

#### Acceptance Criteria
1. Retrieved context includes document freshness metadata.
2. When sources conflict, the agent prefers the newest applicable document by default.
3. Official or priority tags can override freshness when configured.
4. If conflict remains unresolved, the agent explains the conflict and directs the athlete to the athletic department.

## Epic 4: Admin Analytics and Insights

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

## Epic 5: Safety, Governance, and Release Readiness

### US-24
As a platform operator
I want audit logs for admin actions
So that document and role changes are traceable.

> **New in Playbook MVP.** Audit logs are required for admin actions.

#### Acceptance Criteria
1. Document upload, retry, metadata update, and deletion actions are audited.
2. User role changes are audited.
3. Audit entries include actor, action, target type, target ID, timestamp, and metadata.
4. Audit logs are immutable through normal admin UI operations.
5. Audit logs can be queried by super admins.

### US-25
As an athlete
I want emergency and sensitive-topic safeguards
So that Playbook handles high-risk topics responsibly.

> **New in Playbook MVP.** Safety boundaries include NCAA, NIL, FERPA, medical, legal, mental-health, emergency, harassment, and recruiting topics.

#### Acceptance Criteria
1. Emergency requests refuse advice and display emergency instructions.
2. Medical, legal, mental-health, harassment/reporting, and recruiting-risk requests follow configured refusal/escalation policy.
3. NIL and compliance requests answer only when supported by KB context.
4. Safety outcomes are labeled in stored query metadata for admin analytics.
5. Safety policy behavior is covered by automated tests.

### US-26
As a platform operator
I want retrieval and answer-quality evaluations
So that Playbook can be tested before athletes rely on it.

> **New in Playbook MVP.** The product needs quality gates for cited, grounded answers.

#### Acceptance Criteria
1. A golden set covers NIL, compliance, process, emergency, unknown, and conflict scenarios.
2. Retrieval evals measure whether expected documents are retrieved.
3. Answer evals measure accuracy, concision, citation presence, and refusal behavior.
4. Evals run in CI or a documented release validation command.
5. Failing evals block release readiness until reviewed.

### US-27
As a platform operator
I want observability for chat, retrieval, ingestion, and insights
So that failures can be diagnosed quickly.

> **New in Playbook MVP.** The scaffold includes observability hooks that should be made product-specific.

#### Acceptance Criteria
1. Chat runs produce structured logs with request IDs and non-PII metadata.
2. Retrieval logs include document IDs, scores, and ranking metadata without leaking sensitive content.
3. Ingestion logs include stage status and failure reason.
4. Insight jobs log run status, input window, and failure reason.
5. Logs never include secrets or OAuth tokens.

### US-28
As a product owner
I want Playbook to avoid affiliation claims
So that the prototype can use athletics-inspired theming without implying endorsement.

> **New in Playbook MVP.** Specific-school inspiration should be conveyed only through theming, not explicit product or code claims.

#### Acceptance Criteria
1. User-facing copy does not state or imply formal affiliation with a specific university.
2. Code identifiers do not use protected university names as product entities or tenant names.
3. Seed/demo data avoids protected marks unless explicitly provided for authorized demo use.
4. Theming remains configurable for future college rollout.

## Edge Case Summary

| Area | Edge Case | Expected Behavior |
|------|-----------|-------------------|
| Auth | OAuth provider callback fails | No session created; user sees retryable error |
| Auth | Athlete leaves required profile fields blank | Inline validation blocks chat entry |
| Chat | No KB support for policy/process question | Agent declines and directs user to athletic department |
| Chat | Sources conflict | Prefer newest or official/priority source; decline if unresolved |
| Chat | Emergency request | Refuse advice and show emergency instructions |
| Uploads | Admin doc has no extractable text | Mark failed with reason; allow retry/re-upload |
| Uploads | Athlete file unsupported | Reject before generation with clear message |
| Analytics | Query contains athlete name | Analytics view anonymizes owner identity |
| Governance | Athlete hits admin route | Route/API returns unauthorized/forbidden behavior |
