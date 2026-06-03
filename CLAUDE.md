# CLAUDE.md — Agent Harness

> Companion to [AGENTS.md](AGENTS.md). That file has additional architecture detail.
> All rules, skills, and style guides live in `.claude/` — read them before writing code.

This is a reusable agentic-app scaffold: **FastAPI + LangGraph** backend, **Next.js (App Router) + Tailwind v4 + Zustand + TanStack Query** frontend, Anthropic-first LLM. There is no domain product yet — fill in `prd/` and `docs/` as you build.

---

## First Principles

1. **DOCS** -> Read `docs/` before changes. Update docs after changes.
2. **SEARCH** -> Library exists? Use it. (>1k stars, <6mo updated, MIT/Apache)
3. **ASK** -> Unclear? Ask the user. Never assume.
4. **ANALYZE** -> List files changed + dependencies + risks before coding.
5. **PLAN** -> State approach before implementing.
6. **TDD** -> Non-trivial features: write failing test -> implement -> refactor.
7. **VERIFY** -> Tests pass. Requirements met. Docs updated.

---

## When to Ask

Ask before deciding when: multiple approaches exist, requirements are ambiguous, breaking changes needed, new dependencies, or trade-offs involved. Present options, never assume.

---

## Architecture

```
backend/app/ api/v1/ -> services/ -> repositories/ -> models/
frontend/ app/ -> features/ -> components/ -> hooks -> lib/store
kb-service/ api/ -> services/ -> repositories/ -> models/   (+ workers/ Celery pipeline)
```

The backend reaches `kb-service` over HTTP via `LocalKBProvider`
(`backend/app/infrastructure/knowledgebase/`). `kb-service` is the RAG pipeline:
docling parsing -> tiktoken chunking -> OpenAI/LiteLLM embeddings -> pgvector
similarity search. See `kb-service/README.md` and `kb-service/app/infrastructure/STUBS.md`.

---

## Boundaries

| Always | Ask First | Never |
|--------|-----------|-------|
| Search before build | DB schema changes | Secrets in code |
| Inject dependencies | New dependencies | Logic in routes |
| Type everything | API contract changes | `any` type |
| TDD for non-trivial | Auth changes | Skip tests |
| Use structured logging | Breaking changes | Log PII/secrets |
| Test before commit | Log level changes | print() in prod code |

---

## Libraries (Don't Reinvent)

| Need | Use |
|------|-----|
| Auth | fastapi-users |
| UI | Tailwind v4 + Radix UI |
| Server state | TanStack Query |
| Client state | Zustand |
| LLM orchestration | LangGraph + LangChain |
| LLM gateway | LiteLLM |
| Document parsing | Docling (+ python-docx / openpyxl / python-pptx / PyMuPDF) |
| Embeddings | OpenAI (`text-embedding-3-small`) via direct or LiteLLM gateway |
| Vector store | pgvector (`vector(1536)`, HNSW cosine) |
| RAG task queue | Celery + Valkey (`kb-service/app/workers/`) |

---

## Documentation (Read First, Update After)

```
docs/
├── architecture/
│   ├── overview.md
│   ├── db.md
│   └── decisions/          # ADRs
├── api/
│   └── endpoints.md
├── development/
│   ├── bug-log.md
│   ├── tech-debt-tracker.md
│   └── branching-strategy.md
├── guides/
│   ├── setup.md
│   ├── deployment.md
│   ├── contributing.md
│   ├── postgresql_setup.md
│   └── localstack_setup.md
└── agents/
    ├── tools.md
    └── context-engineering.md
```

| Change Type | Update Doc |
|-------------|------------|
| New endpoint | `docs/api/endpoints.md` |
| New tool | `docs/agents/tools.md` |
| Context engineering | `docs/agents/context-engineering.md` |
| Architecture change | Create ADR in `docs/architecture/decisions/` |
| Setup change | `docs/guides/setup.md` |
| Deploy change | `docs/guides/deployment.md` |
| Bug found / tracked | `docs/development/bug-log.md` |
| Tech debt identified | `docs/development/tech-debt-tracker.md` |

---

## Product & Implementation (Read for Context)

```
prd/
├── README.md
├── 01-user-stories/
│   ├── _master-user-stories.md
│   └── epic-*.md
├── 02-technical-docs/
│   ├── data-model.md
│   ├── api-specification.md
│   ├── agentic-framework.md
│   ├── security.md
│   └── integration-spec.md
└── 03-implementation/
    └── _implementation-plan.md
```

| Need | Read |
|------|------|
| User stories | `prd/01-user-stories/_master-user-stories.md` |
| Technical specs | `prd/02-technical-docs/*.md` |
| Implementation plan | `prd/03-implementation/_implementation-plan.md` |

---

## Rules — READ BEFORE EDITING CODE

**IMPORTANT**: Before editing any file, read the applicable rule files listed below. These contain mandatory coding standards that must be followed.

### Always Apply (read for every code change)

| Rule | File |
|------|------|
| TDD Workflow | [.claude/rules/00-tdd.md](.claude/rules/00-tdd.md) |
| SOLID & Patterns | [.claude/rules/01-patterns.md](.claude/rules/01-patterns.md) |
| Security | [.claude/rules/08-security.md](.claude/rules/08-security.md) |
| Logging | [.claude/rules/11-logging.md](.claude/rules/11-logging.md) |
| Documentation MCP | [.claude/rules/10-docs-mcp.md](.claude/rules/10-docs-mcp.md) |

### Apply by File Context

| When editing | Read |
|--------------|------|
| `backend/**/*.py` | [.claude/rules/02-python.md](.claude/rules/02-python.md) |
| `frontend/**/*.tsx` | [.claude/rules/03-react.md](.claude/rules/03-react.md) |
| `frontend/**/*.tsx` | [.claude/rules/13-frontend-design-standards.md](.claude/rules/13-frontend-design-standards.md) |
| `frontend/**/*.{ts,tsx}` | [.claude/rules/14-frontend-code-organization.md](.claude/rules/14-frontend-code-organization.md) |
| `**/agents/**` | [.claude/rules/04-agent.md](.claude/rules/04-agent.md) |
| `**/tests/**` | [.claude/rules/06-testing.md](.claude/rules/06-testing.md) |
| `**/api/**` | [.claude/rules/07-api.md](.claude/rules/07-api.md) |
| `deploy/**/*` | [.claude/rules/05-deployment.md](.claude/rules/05-deployment.md) |
| Git commits | [.claude/rules/09-git.md](.claude/rules/09-git.md) |

---

## Style Guides — READ BEFORE UI WORK

| When working on | Read |
|-----------------|------|
| Design tokens (colors, spacing, radius, type) | [.claude/style/design-tokens.md](.claude/style/design-tokens.md) |
| UI patterns / component styling | [.claude/style/ui-patterns.md](.claude/style/ui-patterns.md) |

---

## Skills — READ BEFORE STARTING TASK

Skills are detailed how-to guides. Read the relevant SKILL.md before starting the task type.

| Task | Skill | References |
|------|-------|------------|
| Implement a feature (TDD) | [.claude/skills/implement-feature/SKILL.md](.claude/skills/implement-feature/SKILL.md) | [tdd-checklist](.claude/skills/implement-feature/references/tdd-checklist.md), [feature-template](.claude/skills/implement-feature/references/feature-template.md) |
| Debug a bug | [.claude/skills/bug-squasher/SKILL.md](.claude/skills/bug-squasher/SKILL.md) | [hypothesis-template](.claude/skills/bug-squasher/references/hypothesis-template.md), [instrumentation-patterns](.claude/skills/bug-squasher/references/instrumentation-patterns.md), [root-cause-checklist](.claude/skills/bug-squasher/references/root-cause-checklist.md) |
| Code review | [.claude/skills/code-review-expert/SKILL.md](.claude/skills/code-review-expert/SKILL.md) | [code-quality-checklist](.claude/skills/code-review-expert/references/code-quality-checklist.md), [security-checklist](.claude/skills/code-review-expert/references/security-checklist.md), [solid-checklist](.claude/skills/code-review-expert/references/solid-checklist.md), [removal-plan](.claude/skills/code-review-expert/references/removal-plan.md) |
| Frontend design / UI work | [.claude/skills/frontend-design/SKILL.md](.claude/skills/frontend-design/SKILL.md) | -- |
| Documentation review | [.claude/skills/doc-gardening/SKILL.md](.claude/skills/doc-gardening/SKILL.md) | [doc-coverage-checklist](.claude/skills/doc-gardening/references/doc-coverage-checklist.md) |
| Code cleanup / tech debt | [.claude/skills/garbage-cleanup/SKILL.md](.claude/skills/garbage-cleanup/SKILL.md) | [cleanup-checklist](.claude/skills/garbage-cleanup/references/cleanup-checklist.md), [code-smell-patterns](.claude/skills/garbage-cleanup/references/code-smell-patterns.md) |
| Context / agent engineering | [.claude/skills/context-engineering/SKILL.md](.claude/skills/context-engineering/SKILL.md) | [reference](.claude/skills/context-engineering/references/reference.md), [examples](.claude/skills/context-engineering/references/examples.md) |
| Sprint progress / status | [.claude/skills/sprint-progress/SKILL.md](.claude/skills/sprint-progress/SKILL.md) | -- |
| Harness / agent setup | [.claude/skills/harness-v2/SKILL.md](.claude/skills/harness-v2/SKILL.md) | -- |
| Handoff / EOD note | [.claude/skills/handoff-note-builder/SKILL.md](.claude/skills/handoff-note-builder/SKILL.md) | [voice-and-structure](.claude/skills/handoff-note-builder/references/voice-and-structure.md), [common-scenarios](.claude/skills/handoff-note-builder/references/common-scenarios.md), [team-and-products](.claude/skills/handoff-note-builder/references/team-and-products.md) |

---

## Commands — Reference Scripts

| Task | Reference |
|------|-----------|
| Start dev services (Postgres, LocalStack, Valkey, backend, frontend) | [.claude/commands/start-services.md](.claude/commands/start-services.md) |
| Git commit conventions | [.claude/commands/git-commits.md](.claude/commands/git-commits.md) |
| Bug squash workflow | [.claude/commands/bug-squasher.md](.claude/commands/bug-squasher.md) |
| Code review workflow | [.claude/commands/code-review.md](.claude/commands/code-review.md) |
| Implement feature workflow | [.claude/commands/implement-feature.md](.claude/commands/implement-feature.md) |
| Doc gardening workflow | [.claude/commands/doc-gardening.md](.claude/commands/doc-gardening.md) |
| Garbage cleanup workflow | [.claude/commands/garbage-cleanup.md](.claude/commands/garbage-cleanup.md) |
| Phase transition | [.claude/commands/next-phase.md](.claude/commands/next-phase.md) |

---

## Quick Reference Commands

```bash
# Deploy (local/dev/test/prod)
./deploy/scripts/deploy.sh local
./deploy/scripts/deploy.sh dev --build --detach

# Backend standalone
cd backend && uvicorn app.main:app --reload && pytest -v

# Frontend standalone
cd frontend && npm run dev && npm test
```
