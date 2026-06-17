---
name: build-plan-writer
description: Use this skill when creating phased build plans, implementation handoffs, feature build breakdowns, phase plans, or docs that let later coding agents implement work one slice at a time. Trigger when the user asks to write, create, update, or review a build plan, phased plan, implementation handoff, direct build breakdown, or agent-ready feature plan.
---

# Build Plan Writer

Create build plans that a later coding agent can implement safely without
re-discovering the whole product. The plan should be grounded in repo facts,
clear about decisions, and split into independently testable phases.

## When to Use

- Creating a phased build plan or implementation handoff.
- Breaking a large feature into slices for later agents.
- Updating an existing build plan after code or scope changes.
- Writing planning docs like `docs/development/*-phased-build.md`.

## Workflow

### 1) Ground in Sources

Before drafting, read the relevant sources:

- Existing build or phase docs in `docs/development/` and `prd/`.
- Product specs, API docs, data model docs, and integration docs related to the feature.
- Current code paths that prove what is already implemented.
- Applicable rules and style guides for any area the future work will touch.

Separate discovered facts from product decisions. Ask only when a decision cannot
be found in docs or code and guessing would materially change the plan.

### 2) Lock Scope and Boundaries

State the current state, target state, and ownership boundaries before phase
details. Include locked decisions or implementation defaults when they prevent
later ambiguity.

Always make these boundaries explicit when relevant:

- Which service owns each responsibility.
- Which public routes, schemas, or contracts change.
- Which data, auth, privacy, and logging constraints must hold.
- Which work is deliberately out of scope.

Never let clients choose trusted server-side metadata such as source ownership,
authorization scope, storage internals, or service-internal identifiers.

### 3) Break Work into Phases

Each phase should be small enough for a coding agent to complete and verify on
its own. Prefer this structure:

```markdown
## Phase N: Short Title

Scope:
- ...

Suggested files:
- `path/to/file`

Acceptance criteria:
- ...

Relevant tests:
- ...

Do not do yet:
- ...
```

Use `[IMPLEMENTED]`, `[COMPLETED]`, or similar status markers only when code and
docs actually prove that status. Keep planned work clearly separate from
implemented behavior.

### 4) Add Cross-Phase Safety Nets

Include a cross-phase test matrix for broad plans. Add implementation notes,
explicit non-goals, and open follow-ups when they prevent likely mistakes.

Common acceptance coverage:

- Request/response contract shape.
- Authorization and ownership checks.
- Idempotency and retry behavior.
- Failure states and sanitized error handling.
- Logging without secrets, raw document text, signed URLs, or large model inputs.
- Docs updated only after behavior is implemented.

### 5) Write for Later Agents

Plans should be concrete enough to execute but not overfit internals that the
request has not settled. Avoid speculative migrations, dependencies, schemas,
wire shapes, and fallback policies unless they are necessary to prevent a real
implementation mistake.

Use `references/build-plan-template.md` when starting a new plan from scratch.

## Output Rules

- Use Markdown.
- Prefer concise prose and short bullets.
- Name suggested files only where they disambiguate likely edit locations.
- Keep implementation phases independently testable.
- Clearly label planning artifacts as not yet implemented.
- Do not include secrets, private credentials, raw file contents, raw model
  inputs, or signed/presigned URLs.

