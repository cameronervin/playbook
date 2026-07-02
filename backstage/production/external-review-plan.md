# External Review Plan

Last updated: July 2, 2026

## Goal

Schedule a scoped external review after P0 automation is green. The initial
review targets the web app, API, LLM/data-handling boundaries, and production
readiness evidence rather than a full cloud/IAM penetration test.

Keep this P1 gate open until scheduling evidence exists with owner, target
date/window, scope, vendor/reviewer, and tracking link.

## Scope

| Area | In scope |
|------|----------|
| Frontend | Authenticated athlete/admin flows, protected routes, upload UI, legal/security pages. |
| Backend API | Auth/authz, admin APIs, chat/admin chat, uploads, rate limits, audit logging. |
| KB service | Service auth, ingest/search contracts, source scoping, private file boundaries. |
| LLM/data handling | LiteLLM key separation, prompt/source redaction, refusal behavior, eval evidence. |
| Observability | Sentry/Langfuse privacy scrubbers and alert/smoke evidence. |
| Release evidence | CI release command, scanner/SBOM/DAST artifacts, load-test hooks, recovery hooks. |

Out of scope for the first review unless explicitly added: social engineering,
physical security, full cloud account/IAM review, destructive testing, and
production data exfiltration tests.

## Reviewer Requirements

- Cite the OWASP Web Security Testing Guide version used for web/API testing.
  Do not cite only `latest` or `stable` because those labels can change.
- Use non-production accounts and synthetic data unless a written exception
  exists.
- Do not request or store production secrets, prompts, source text, signed URLs,
  athlete identity, or raw IP addresses in the final report.
- Provide severity, affected component, reproduction notes, evidence summary,
  remediation recommendation, and retest result for each finding.

## Scheduling Evidence

Fill this before marking the gate complete:

| Field | Value |
|-------|-------|
| Review owner | `<TBD>` |
| Reviewer/vendor | `<TBD>` |
| Target date/window | `<TBD>` |
| Scope approved by | `<TBD>` |
| Tracking link | `<TBD>` |
| P0 automation evidence | `<workflow/run/artifact pointers>` |

## Review Packet

Provide the reviewer with sanitized pointers to:

- `backstage/prd/03-implementation/_production-readiness-playbook.md`
- `backstage/production/coverage-policy.md`
- `backstage/production/incident-runbook.md`
- `backstage/production/data-lifecycle.md`
- `backstage/guides/security_scanning.md`
- `backstage/guides/deployment.md`
- `backstage/security/evidence/README.md`

## Exit Criteria

- Critical/high findings are remediated or have accepted risk with owner,
  expiry, mitigation, and rollback path.
- Retest evidence exists for remediated critical/high findings.
- Medium/low findings are triaged into tracked work.
- Final report location and sanitized summary are linked from release evidence.
