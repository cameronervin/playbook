# Product Requirements (PRD)

> This directory holds the product spec a new team fills in to build the
> application. It is organized so user stories, technical contracts, and the
> implementation plan stay linked and traceable. Replace the `Example` content
> with your own product.

## Structure

```
prd/
├── README.md                          # This file
├── 01-user-stories/
│   ├── _master-user-stories.md        # Consolidated stories + rollup table
│   └── epic-1-example.md              # One file per epic
├── 02-technical-docs/
│   ├── data-model.md                  # Entities, relationships, constraints
│   ├── api-specification.md           # Endpoints, contracts, status codes
│   ├── agentic-framework.md           # Agent runtime: chains/nodes/graphs/executors/tools
│   ├── security.md                    # Auth, validation, secrets, CORS
│   └── integration-spec.md            # LLM provider, knowledge base, storage
└── 03-implementation/
    ├── _implementation-plan.md        # Phase overview table
    └── phase-1-foundations.md         # One file per phase, with task tables
```

## How to Use It

1. **Define scope** — write user stories in `01-user-stories/`, grouped into
   epics. Give each story a contiguous ID (`US-01`, `US-02`, …) and acceptance
   criteria.
2. **Specify the technicals** — capture the data model, API contracts, agent
   framework, security, and integration requirements in `02-technical-docs/`.
3. **Plan the build** — break work into phases in `03-implementation/`. Each
   phase maps tasks to user stories and a validation chain.
4. **Execute and track** — work phase tasks in order, updating their status
   symbols as you go. Keep specs in sync with what's actually built.

## Status Symbols

Use these in phase task tables:

- ☐ — Not started
- ◐ — Partial (note what remains in the Goal column)
- ☑ — Complete (reviewed, tested, committed)

## Deviation Logging

When implementation diverges from a planned task, record it in the phase file:

- **Planned** — what the task said to do.
- **Actual** — what was actually built.
- **Reason** — why it changed.
- **Impact** — effect on later phases.
