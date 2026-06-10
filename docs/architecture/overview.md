# Architecture Overview

> Template — replace the `Example` domain entity and any placeholder names with your product's concepts.

## System Diagram
```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend                              │
│  Next.js (App Router) + TypeScript + Tailwind v4            │
│  TanStack Query (server state) + Zustand (client state)     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     API Gateway (nginx)                      │
│  Serves frontend, proxies /api → backend                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Backend                         │
│  API → Services → Repositories → Models                     │
│  Agents (LangGraph) → Chains → Nodes → Graphs → Executors   │
└─────────────────────────────────────────────────────────────┘
              │                               │
    ┌─────────┴─────────┬─────────────────────┴───────────────┐
    ▼                   ▼                                     ▼
┌──────────────┐  ┌──────────────┐       ┌─────────────────────────────┐
│  PostgreSQL  │  │  AWS S3 /    │       │   LLM Providers             │
│ Data storage │  │  MinIO       │       │   Direct (Anthropic-first)  │
│              │  │ File storage │       │   or LiteLLM               │
└──────────────┘  └──────────────┘       └─────────────────────────────┘
       │
       ▼
┌──────────────┐   (optional async)
│ Valkey + Celery │  background jobs / polled tasks / agent stream events
└──────────────┘
```

## Layers

### Backend
```
app/
├── api/v1/            # HTTP endpoints (thin — parse, call service, return)
├── services/          # Business logic, orchestration
├── repositories/      # Data access (all DB access goes through here)
├── models/            # SQLAlchemy 2.0 ORM (Mapped[] types)
├── schemas/           # Pydantic DTOs (request/response)
├── agents/            # LangGraph orchestration
│   ├── chains/        # Per-task LLM chains
│   ├── nodes/         # Graph nodes (load/save state, router, etc.)
│   ├── graphs/        # Graph assembly (wires nodes into a runnable graph)
│   ├── executors/     # Run/resume a graph, manage checkpoints
│   ├── context/       # Context injection policies and serializers
│   ├── prompts/       # Task-specific prompts
│   └── tools/         # Agent tools (e.g. example_tool)
└── infrastructure/    # External integrations
    ├── db/            # SQLAlchemy engine/session helpers
    ├── storage/       # S3 client (boto3)
    ├── llm/           # LLM providers (direct + LiteLLM)
    ├── streaming/     # Valkey Streams/pub-sub agent event adapter
    └── workers/       # Celery app + worker tasks (optional)
```

### Frontend
```
src/
├── app/             # Next.js App Router routes (layouts, pages, route handlers)
├── components/      # Reusable UI and feature components
│   ├── ui/          # Reusable, stateless UI primitives
│   └── features/    # Feature-specific components
├── hooks/           # App-wide hooks
├── lib/             # API client, constants, Zustand stores, utils
└── types/           # TypeScript type definitions
```

## Tech Stack
| Layer | Technology |
|-------|------------|
| Frontend | Next.js (App Router), TypeScript, Tailwind v4, TanStack Query, Zustand |
| Backend | FastAPI, SQLAlchemy 2.0 (async), Pydantic, Alembic |
| Agents | LangGraph, LangChain |
| LLM | LiteLLM by default in deployed environments; direct Anthropic/OpenAI only for local or break-glass use |
| Database | PostgreSQL |
| Storage | AWS S3, MinIO (local dev) |
| Async (optional) | Valkey (broker/backend, Streams/pub-sub for agent responses) + Celery |
| Observability | structlog |
| Deploy | Docker Compose, nginx |

## Provider / Factory Pattern

LLM access is abstracted behind a provider factory so the rest of the app never
imports a vendor SDK directly:

- A `BaseLLMProvider` exposes `get_chat_model()` (and streaming/structured
  variants). Application code and agents depend on this abstraction, not on a
  concrete client.
- Transport is selected by `LLM_PROVIDER_MODE`:
  - `litellm` — route through a LiteLLM proxy (OpenAI-compatible) for
    centralized credentials, model aliases, routing, fallbacks, spend tracking,
    and cost/rate controls.
  - `direct` — call the provider SDK directly for local development, smoke
    tests, or an explicit break-glass path.
- Swapping a model or provider is a config change, not a code change. See
  [ADR 0002](decisions/0002-llm-provider-modes.md).

The same pattern applies to storage (an S3-compatible client that points at
MinIO in local development and real S3 in production), agent streaming (Valkey
Streams for ordered task events plus pub/sub wake-ups), and any other swappable
infrastructure.

## Request Lifecycle

1. **Frontend** issues a request via the typed API client (TanStack Query).
2. **nginx** routes `/api/*` to the backend.
3. **Route** (`api/v1/`) validates input with a Pydantic schema, then calls a
   service. Routes stay thin (no business logic, no SQL).
4. **Service** runs business logic, orchestrates repositories, and — for LLM
   work — invokes an agent graph through an **executor**.
5. **Repository** performs data access via SQLAlchemy `select()` statements.
6. **Agent executor** (when involved) runs/resumes a LangGraph graph, persisting
   checkpoints to Postgres so long runs can resume by `thread_id`.
7. **Service** returns a DTO; the **route** serializes it via `response_model`.
8. Long-running work is offloaded to **Celery** workers and is usually polled by
   task/run status, such as KB ingestion and dashboard insight runs. Interactive
   agent responses are the exception: athlete chat and admin chat workers publish
   ordered stream events to **Valkey Streams** and pub/sub, and HTTP stream
   endpoints subscribe by validated `task_id` to forward chunks, completion, or
   error events to the frontend.
