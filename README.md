# Agentic App Scaffold

A reusable, **pattern-faithful** starting point for building an agentic application with a
**FastAPI + LangGraph** backend, a **Next.js (App Router)** frontend, and a full
**Claude Code / Cursor agent harness** (`.claude/`, `.cursor/`, `CLAUDE.md`, `AGENTS.md`).

This scaffold was distilled from a production codebase. All domain logic has been removed and
replaced with clearly-labeled `example_*` exemplars + `STUBS.md` notes, so a coding agent can
pattern-match against real architecture instead of starting from an empty repo.

---

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, SQLAlchemy 2.0 (async), Alembic, Pydantic v2 |
| Agents | LangGraph + LangChain (Anthropic-first) |
| LLM gateway | LiteLLM (optional `gateway` mode) |
| Storage | S3 / LocalStack (boto3) |
| Frontend | Next.js (App Router), Tailwind CSS v4, Zustand, TanStack Query |
| KB / RAG | `kb-service`: docling → OpenAI embeddings → pgvector (FastAPI + Celery) |
| Async | Celery + Valkey (optional) |
| Logging | structlog |
| Tests | pytest (backend / kb-service), Vitest + React Testing Library (frontend) |

---

## Architecture

```
backend/app/  api/v1 -> services -> repositories -> models
frontend/     app/ -> features/ -> components/ -> hooks -> lib/store
```

- **Thin routes** parse the request and delegate to a service (`Depends()` DI).
- **Services** hold business logic and orchestrate repositories + providers.
- **Repositories** are the only place that touches the DB (`select()` + `selectinload`).
- **Infrastructure providers** (LLM / KB / storage) follow an **ABC + `StrEnum` mode + `@lru_cache` factory** pattern so implementations are swappable by config.
- **Agents** compose `chains -> nodes -> graphs -> executors` via builders; tools are declared in a frozen `ToolSpec` registry.

---

## What's where

| Path | Purpose |
|------|---------|
| `CLAUDE.md` / `AGENTS.md` | Agent harness manifesto (rules, skills, boundaries) |
| `.claude/` `.cursor/` | Rules, skills, style guides, commands, MCP config |
| `backend/app/infrastructure/` | LLM / KB / storage providers + LangGraph checkpointer (see `INFRASTRUCTURE.md`) |
| `backend/app/agents/` | LangGraph orchestration (see `agents/STUBS.md`) |
| `kb-service/` | Standalone RAG service: docling → OpenAI embeddings → pgvector. The backend's `LocalKBProvider` is its HTTP client (see `kb-service/README.md`) |
| `frontend/` | Next.js skeleton (see `FRONTEND.md`) |
| `docs/` | Architecture, API, guides, ADRs |
| `prd/` | Product requirements skeleton (user stories, tech docs, phases) |
| `deploy/` | Docker Compose, Dockerfiles, env templates, scripts |

Every `STUBS.md` explains how to replace the `example_*` exemplar with real logic.

---

## First steps for a new agent

1. Read `CLAUDE.md` and the rules in `.claude/rules/`.
2. Read `docs/architecture/overview.md` and `prd/README.md`.
3. Pick a layer, open its `example_*` exemplar + neighbouring `STUBS.md`, and follow the pattern.
4. Backend: `cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload`.
5. Frontend: `cd frontend && npm install && npm run dev`.

> This is scaffolding, not a running product. The example flows parse and type-check, but real
> models, providers, prompts, and screens are intentionally left as stubs.
