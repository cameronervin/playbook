# Playbook

Playbook is an agentic web prototype for college athletic departments. The MVP
gives athletes a chat-first support experience for NIL, compliance, and internal
process questions, grounded in department-specific knowledge and supported by
admin analytics.

The project is an MVP build in progress. It builds on a reusable FastAPI,
LangGraph, Next.js, and knowledge-base service foundation, but the product goal
is Playbook: a neutral, athlete-first support tool that does not imply
affiliation with any specific university.

---

## MVP Focus

| Surface | Purpose |
|---------|---------|
| Athlete chat | Ask natural-language NIL, compliance, and process questions, with grounded answers, citations, conversation history, and conversation-scoped file uploads. |
| Knowledge base operations | Let admins upload, tag, process, retry, and manage department documents used for retrieval. |
| Admin analytics | Help admins understand question volume, topic patterns, unsupported requests, and recurring knowledge gaps. |
| Safety and governance | Support refusal behavior, role-based access, audit logging, anonymized analytics, and release-readiness checks. |

MVP priorities are a low-friction athlete entry path, concise cited answers,
safe declines for unsupported or sensitive topics, admin document management,
and insight generation for department operators.

---

## Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js App Router, TypeScript, Tailwind CSS v4, Zustand, TanStack Query |
| Backend | FastAPI, SQLAlchemy 2.0 async, Alembic, Pydantic v2 |
| Agents | LangGraph + LangChain, Anthropic-first LLM orchestration |
| LLM gateway | LiteLLM gateway mode, with direct provider mode for local or break-glass use |
| Knowledge base | Standalone `kb-service` for ingestion, chunking, embeddings, and retrieval |
| Retrieval | Docling, tiktoken chunking, OpenAI/LiteLLM embeddings, pgvector similarity search |
| Data and storage | PostgreSQL, pgvector, S3 or LocalStack |
| Async work | Celery + Valkey for long-running ingestion and background processing |
| Observability | structlog, audit logs, and privacy-conscious operational logging |
| Tests | pytest for backend and KB service, Vitest + React Testing Library for frontend |

---

## Architecture

```text
frontend/     app/ -> features/ -> components/ -> hooks -> lib/store
backend/app/  api/v1 -> services -> repositories -> models
kb-service/   api -> services -> repositories -> models + workers
```

Playbook separates the product API, frontend experience, and retrieval pipeline:

- The **Next.js frontend** provides the athlete chat surface and admin
  workspaces.
- The **FastAPI backend** owns product APIs, auth, roles, conversations, audit
  logging, analytics, and LangGraph agent orchestration.
- The **LangGraph agent layer** composes chains, nodes, graphs, executors,
  prompts, and tools for chat, safety, retrieval, and insight workflows.
- The **KB service** owns document ingestion and retrieval: parsing, chunking,
  embedding, pgvector storage, status tracking, and search.
- The backend talks to the KB service over HTTP through `LocalKBProvider`, so
  retrieval can evolve independently from the product API.

---

## Repository Map

| Path | Purpose |
|------|---------|
| `prd/` | Playbook user stories, technical specs, and phase implementation plans |
| `docs/` | Architecture notes, API docs, setup guides, ADRs, and agent documentation |
| `backend/` | FastAPI product backend, LangGraph agent runtime, providers, models, and tests |
| `frontend/` | Next.js App Router frontend for athlete and admin experiences |
| `kb-service/` | Standalone RAG service for document ingestion and vector retrieval |
| `deploy/` | Docker Compose, Dockerfiles, environment templates, and deployment scripts |
| `.claude/`, `.cursor/`, `AGENTS.md`, `CLAUDE.md` | Agent harness rules, skills, commands, and collaboration guidance |

---

## Getting Oriented

Start with the product docs, then follow the implementation phase plan:

1. Read [`prd/README.md`](prd/README.md) for the MVP overview, priorities, and
   document index.
2. Read [`prd/03-implementation/_implementation-plan.md`](prd/03-implementation/_implementation-plan.md)
   for the phase roadmap.
3. Read [`docs/architecture/overview.md`](docs/architecture/overview.md) for the
   system architecture and request lifecycle.
4. Use [`docs/guides/setup.md`](docs/guides/setup.md) for local setup details.
5. Use [`kb-service/README.md`](kb-service/README.md) when working on ingestion,
   embeddings, or retrieval.

For code changes, follow the rules and skills in `.claude/` before editing.
Those files define the repo workflow for TDD, security, logging,
documentation, frontend design, and review.
