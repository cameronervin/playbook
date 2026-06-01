# Contributing

> How to make changes safely. Read the rules in `.claude/rules/` before editing
> code — they are mandatory.

## First Principles

1. **Read docs first** — check `docs/` and the relevant rule files before
   changing anything.
2. **Search before you build** — prefer a maintained library over reinventing.
3. **Ask when unclear** — never assume on ambiguous requirements, breaking
   changes, new dependencies, or trade-offs.
4. **TDD for non-trivial work** — write a failing test, make it pass, refactor.
5. **Verify** — tests pass, requirements met, docs updated.

## TDD Workflow

For non-trivial features (new logic, new endpoints, refactors, bug fixes):

```
1. RED      → write a failing test that describes the behavior
2. GREEN    → write the minimal code to make it pass
3. REFACTOR → clean up, keep tests green
```

Skip TDD only for config changes, trivial CRUD, dependency bumps, and docs.

## Architectural Boundaries

| Layer | Responsibility | Must NOT contain |
|-------|----------------|------------------|
| Route (`api/v1`) | Parse request, call service, return response | Business logic, SQL |
| Service | Business logic, orchestration | HTTP concerns |
| Repository | Data access via `select()` | Business decisions |
| Model | SQLAlchemy ORM | — |
| Agent (chains/nodes/graphs/executors) | LLM orchestration | Vendor SDK imports — use the provider factory |

- Inject dependencies with `Depends()`.
- Type everything; never use `any`.
- Use structured logging (`structlog`); never log secrets or PII.
- Validate all input with Pydantic.

## Pull Request Flow

1. Branch from `develop`: `feature/<description>` or `bugfix/<description>`.
2. Make atomic commits using Conventional Commits (`feat:`, `fix:`, `docs:`, …).
3. Add/adjust tests. Run the full suite locally.
4. Update any affected docs (see the table below).
5. Open a PR to `develop`. Ensure CI passes and request review.
6. Squash/merge once approved.

See [branching-strategy.md](../development/branching-strategy.md) for the full
model.

## Update Docs After Changes

| Change | Update |
|--------|--------|
| New/changed endpoint | `docs/api/endpoints.md` |
| New agent tool | `docs/agents/tools.md` |
| Schema change | `docs/architecture/db.md` + Alembic migration |
| Architecture decision | New ADR in `docs/architecture/decisions/` |
| Setup change | `docs/guides/setup.md` |
| Deploy change | `docs/guides/deployment.md` |
| Bug found | `docs/development/bug-log.md` |
| Tech debt taken on | `docs/development/tech-debt-tracker.md` |

## Pre-Commit Checklist

- [ ] Tests written/updated and passing
- [ ] Types complete, no `any`
- [ ] No secrets, PII, or `print()` in committed code
- [ ] Docs updated for the change
- [ ] Conventional commit message
