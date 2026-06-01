# Phase 1 — Foundations

> Stand up the project skeleton, data model, authentication, core API contracts,
> and local infrastructure. This phase unblocks all feature work.

## Goal

A running backend + frontend with auth, the `Example` data model, migrations,
and the `Example` CRUD contract — all locally runnable via Docker Compose.

## Task Table

| Status | Task | Goal | User Stories | Validation |
|--------|------|------|--------------|------------|
| ☐ | Project skeleton | Backend (FastAPI) and frontend (Next.js) scaffolds run locally | — | `uvicorn` serves `/api/v1/health`; `npm run dev` serves the app |
| ☐ | Local infrastructure | Postgres, LocalStack, Valkey run via compose | — | `./deploy/scripts/deploy.sh local` brings services up; `validate-db.sh` passes |
| ☐ | Auth | `fastapi-users` register/login/me wired up | — | Register → login → `/auth/users/me` returns the user; protected route rejects anonymous |
| ☐ | Data model + migration | `Example` model + Alembic migration | US-01 | `alembic upgrade head` creates the table with indexes and FK |
| ☐ | Repository layer | `ExampleRepository` (CRUD via `select()`) | US-01, US-02 | Repo unit tests pass against a test DB |
| ☐ | Service layer | `ExampleService` (ownership scoping, validation, DTOs) | US-01, US-02 | Service tests cover create/list/get/update/delete and ownership rules |
| ☐ | API layer | `/api/v1/examples` routes with `response_model` | US-01, US-02 | Endpoints return correct status codes; contract matches `api-specification.md` |
| ☐ | Provider factory | `BaseLLMProvider.get_chat_model()` with `direct`/`gateway` modes | — | A smoke call succeeds in `direct` mode against a cheap model |

## Validation Chain

```
compose up → migrations apply → auth works → Example CRUD contract established
   and tested → provider factory returns a working chat model
```

## Definition of Done

- [ ] `./deploy/scripts/deploy.sh local` starts all services healthy
- [ ] `alembic upgrade head` applies cleanly from an empty DB
- [ ] Auth register/login/me works and protects routes
- [ ] `Example` CRUD endpoints match `prd/02-technical-docs/api-specification.md`
- [ ] Ownership scoping enforced (404 on others' resources)
- [ ] Repository + service tests pass
- [ ] `docs/` updated (endpoints, db) to match what was built

## Deviation Log

> Record divergences here as: Planned / Actual / Reason / Impact.

_None yet._
