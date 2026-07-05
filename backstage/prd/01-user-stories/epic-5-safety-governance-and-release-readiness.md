# Epic 5: Safety, Governance, and Release Readiness

## Epic Goal

Make Playbook safe enough for a real athlete-facing prototype: admin actions are auditable, sensitive topics are handled responsibly, and answer quality can be evaluated before launch.

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

## Edge Cases

| Edge Case | Expected Behavior |
|-----------|-------------------|
| Emergency query appears in chat | Agent refuses advice and shows emergency instructions |
| Admin attempts to edit audit logs | Operation is unavailable through normal UI/API |
| Eval dataset fails a release gate | Release readiness remains blocked until reviewed |
| Theming request includes protected affiliation copy | Copy is rejected or changed to neutral language |
