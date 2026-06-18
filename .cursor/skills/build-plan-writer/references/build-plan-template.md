# <Feature Name> Phased Build

## Purpose

Describe why this build plan exists, what outcome it enables, and how later
coding agents should use it. State clearly whether this is a planning artifact
or a description of implemented behavior.

Default location for new build plans:

- `backstage/build-plans/<descriptive-kebab-name>-phased-build.md`

Primary source documents:

- `path/to/source.md`
- `path/to/related-spec.md`

## Current State

Summarize what the repo does today. Include only facts confirmed from docs or
code. Call out important gaps, existing seams, and compatibility constraints.

## Target Architecture

Describe the intended end state at the service, API, data, or workflow level.
Use a small table or ASCII diagram when ownership or data flow could be
misread.

## Locked Decisions or Implementation Defaults

| Decision | Direction |
|----------|-----------|
| Example decision | Example locked direction |

## Ownership and Boundary Rules

- State which service or layer owns each responsibility.
- State which clients or callers are allowed to choose which inputs.
- State auth, privacy, logging, storage, and data-leakage constraints.
- State what must remain internal.

## Phase 0: Contracts and Docs Baseline

Scope:

- Define or reconcile contracts and docs needed before runtime work.

Suggested files:

- `path/to/doc-or-schema`

Acceptance criteria:

- Later coding agents can see the intended behavior without reading the entire
  repo.
- No runtime behavior changes are required unless explicitly stated.

Relevant tests:

- Contract/schema tests if runtime contract files change.

Do not do yet:

- Do not implement runtime behavior in a docs-only baseline phase.

## Phase 1: <Short Implementation Slice>

Scope:

- Implement one independently testable slice.

Suggested files:

- `path/to/file`

Acceptance criteria:

- Observable behavior or contract guarantee.
- Safety and authorization guarantee.

Relevant tests:

- Unit, integration, component, smoke, or manual checks that prove the phase.

Do not do yet:

- Work intentionally deferred to later phases.

## Phase 2: <Next Implementation Slice>

Scope:

- Continue with the next bounded slice.

Suggested files:

- `path/to/file`

Acceptance criteria:

- Observable behavior or contract guarantee.

Relevant tests:

- Tests or checks that prove this slice without requiring later phases.

Do not do yet:

- Work intentionally deferred to later phases.

## Cross-Phase Test Matrix

| Area | Required scenarios |
|------|--------------------|
| Contracts | Request/response validation and safe response shape |
| Authorization | Role, ownership, and cross-scope denial cases |
| Failure handling | Retryable failures, terminal failures, sanitized reasons |
| Idempotency | Duplicate calls, duplicate workers, or repeated tasks |
| Security/logging | No secrets, raw large text, signed URLs, or private data in logs |
| Docs | Docs updated only when behavior is implemented |

## Implementation Notes

- Preserve existing ownership boundaries unless the plan explicitly changes
  them.
- Prefer existing providers, repositories, hooks, and service seams over new
  abstractions.
- Track shortcuts or deferred cleanup in `backstage/development/tech-debt-tracker.md`
  when relevant.

## Explicit Non-Goals

- No unrelated refactors.
- No new dependencies unless explicitly approved.
- No API, schema, auth, or migration changes outside the stated phases.

## Open Follow-Ups

- List decisions intentionally left for later after implementation evidence,
  product feedback, or performance data exists.
