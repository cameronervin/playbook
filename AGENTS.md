# Agent Platform

A reusable agentic-app scaffold: **FastAPI + LangGraph** backend, **Next.js (App Router) + Tailwind v4 + Zustand + TanStack Query** frontend, Anthropic-first LLM via LiteLLM. No domain product yet — fill in `prd/` and `docs/` as you build.

## First Principles
1. **DOCS** -> Read `docs/` before changes. Update docs after changes.
2. **SEARCH** -> Library exists? Use it. (>1k stars, <6mo updated, MIT/Apache)
3. **ASK** -> Unclear? Ask the user. Never assume.
4. **ANALYZE** -> List files changed + dependencies + risks before coding.
5. **PLAN** -> State approach before implementing.
6. **TDD** -> Non-trivial features: write failing test -> implement -> refactor.
7. **VERIFY** -> Tests pass. Requirements met. Docs updated.

## When to Ask
Ask before deciding when: multiple approaches exist, requirements are ambiguous, breaking changes needed, new dependencies, or trade-offs involved. Present options, never assume.

## Architecture
```
backend/app/ api/v1/ -> services/ -> repositories/ -> models/
frontend/ app/ -> features/ -> components/ -> hooks -> lib/store
```

## Boundaries
| ✅ Always | ⚠️ Ask First | 🚫 Never |
|-----------|--------------|----------|
| Search before build | DB schema changes | Secrets in code |
| Inject dependencies | New dependencies | Logic in routes |
| Type everything | API contract changes | `any` type |
| TDD for non-trivial | Auth changes | Skip tests |
| Use structured logging | Breaking changes | Log PII/secrets |
| Test before commit | Log level changes | print() in prod code |

## Libraries (Don't Reinvent)
| Need | Use |
|------|-----|
| Auth | fastapi-users |
| UI | Tailwind v4 + Radix UI |
| Server state | TanStack Query |
| Client state | Zustand |
| LLM orchestration | LangGraph + LangChain |
| LLM gateway | LiteLLM |

## Documentation (Read First, Update After)
```
docs/
├── architecture/
│   ├── overview.md       # System diagram & layers
│   ├── db.md             # Database schema
│   └── decisions/        # ADRs
├── api/
│   └── endpoints.md      # API reference
├── development/
│   ├── bug-log.md        # Bug tracking
│   ├── tech-debt-tracker.md
│   └── branching-strategy.md
├── guides/
│   ├── setup.md          # Local setup
│   ├── deployment.md     # Deploy commands
│   ├── contributing.md   # Dev workflow
│   ├── postgresql_setup.md
│   └── localstack_setup.md  # S3 emulation
└── agents/
    ├── tools.md          # Agent tools (LangChain @tool)
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

## Product & Implementation (Read for Context)
```
prd/
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

## Rules (Load by Context)
| When editing | Load |
|--------------|------|
| Any code | `@.cursor/rules/00-tdd.mdc` |
| Any code | `@.cursor/rules/01-patterns.mdc` |
| Any code | `@.cursor/rules/08-security.mdc` |
| Any code | `@.cursor/rules/11-logging.mdc` |
| Any code | `@.cursor/rules/10-docs-mcp.mdc` |
| `backend/**/*.py` | `@.cursor/rules/02-python.mdc` |
| `frontend/**/*.tsx` | `@.cursor/rules/03-react.mdc` |
| `frontend/**/*.tsx` | `@.cursor/rules/13-frontend-design-standards.mdc` |
| `frontend/**/*.{ts,tsx}` | `@.cursor/rules/14-frontend-code-organization.mdc` |
| `**/agents/**` | `@.cursor/rules/04-agent.mdc` |
| `**/tests/**` | `@.cursor/rules/06-testing.mdc` |
| `**/api/**` | `@.cursor/rules/07-api.mdc` |
| `deploy/**/*` | `@.cursor/rules/05-deployment.mdc` |
| Git commits | `@.cursor/rules/09-git.mdc` |

## Commands
```bash
# Deploy (local/dev/test/prod)
./deploy/scripts/deploy.sh local
./deploy/scripts/deploy.sh dev --build --detach

# Backend standalone
cd backend && uvicorn app.main:app --reload && pytest -v

# Frontend standalone
cd frontend && npm run dev && npm test
```
