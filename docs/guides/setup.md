# Local Setup

> Get the backend and frontend running locally. Replace placeholder repo URLs
> and names with your own.

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.12+ | Backend (FastAPI) |
| uv | latest | Python package and environment manager |
| Node.js | 20+ | Frontend (Next.js) |
| Docker | latest | Postgres, MinIO, Valkey |
| Git | latest | — |

## 1. Clone

```bash
git clone <your-repo-url> agentic-app
cd agentic-app
```

## 2. Start Infrastructure

Start Postgres, MinIO, Valkey, KB-service, and LiteLLM via Docker Compose:

```bash
cp deploy/envs/.env.local.example deploy/envs/.env.local
cp deploy/envs/.env.kb-service.local.example deploy/envs/.env.kb-service.local
cp deploy/envs/.env.litellm.local.example deploy/envs/.env.litellm.local
./deploy/scripts/deploy.sh local --build
```

Edit `deploy/envs/.env.litellm.local` before making real model calls. Provider
API keys, such as `OPENAI_API_KEY`, belong in that LiteLLM-only env file, not in
backend or KB-service env files. OpenAI regional projects also need
`OPENAI_API_BASE`, for example `https://us.api.openai.com/v1`. For first local
boot, the backend and KB-service examples use `sk-local-litellm-master-key` as
their LiteLLM service key; after LiteLLM starts, generate a scoped key from
`http://localhost:4000/ui` and replace `LITELLM_API_KEY` in the backend and
KB-service env files.

Verify LiteLLM:

```bash
curl http://localhost:4000/health/liveliness
curl http://localhost:4000/health/readiness
```

See [Self-Hosted LiteLLM](litellm_self_hosting.md) for key provisioning and
security notes.

Or start only the services you need — see
[postgresql_setup.md](postgresql_setup.md) and
[minio_setup.md](minio_setup.md).

## 3. Backend

```bash
cd backend

# Install Python 3.12 if needed, then create/sync the managed environment
uv python install 3.12
uv sync

# Configure environment
cp ../deploy/envs/.env.local .env
# If running backend directly on the host, set:
# LITELLM_BASE_URL=http://localhost:4000

# Apply database migrations
uv run alembic upgrade head

# Run the dev server (http://localhost:8000)
uv run uvicorn app.main:app --reload
```

Verify: `curl http://localhost:8000/api/v1/health` → `{"status": "healthy"}`.

Optional backend worker for Phase 2+ async jobs:

```bash
uv run celery -A app.workers.app:backend_worker worker -Q backend-agent,backend-files,backend-insights,backend-maintenance --concurrency=2 --loglevel=info
```

The backend worker and future interactive agent stream endpoints use the app
Valkey service. For Docker Compose this is:

```env
CELERY_BROKER_URL=redis://valkey:6379/0
CELERY_RESULT_BACKEND=redis://valkey:6379/1
AGENT_STREAM_VALKEY_URL=redis://valkey:6379/2
```

When running the backend directly on the host, use
`AGENT_STREAM_VALKEY_URL=redis://localhost:6379/2`.

Phase 1 auth and KB document control-plane settings:

```env
API_PUBLIC_URL=http://localhost:8000
OAUTH_STATE_SECRET=replace-with-a-long-random-value
DEV_AUTH_ENABLED=false
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
MICROSOFT_OAUTH_CLIENT_ID=
MICROSOFT_OAUTH_CLIENT_SECRET=
MICROSOFT_OAUTH_TENANT=common
DEFAULT_ORGANIZATION_NAME=Playbook Athletics
DEFAULT_ORGANIZATION_SLUG=playbook-athletics
KB_WEBHOOK_SECRET=replace-with-a-long-random-value
```

For Google and Microsoft app registrations, set redirect URIs to:

```text
http://localhost:8000/api/v1/auth/google/callback
http://localhost:8000/api/v1/auth/microsoft/callback
```

Browser OAuth callbacks set the Playbook session cookie and redirect to
`FRONTEND_URL + next_route`, usually `/profile` for incomplete athletes or
`/chat` for complete profiles. API-style callers that do not request
`text/html` still receive the JSON `SessionResponse`.

For local UI validation without Google/Microsoft OAuth, set
`DEV_AUTH_ENABLED=true` while `ENVIRONMENT=local` and `DEBUG=true`, then use the
Developer SSO provider on the login screen or open one of these backend URLs in
the same browser you use for the frontend:

```text
http://localhost:8000/api/v1/auth/dev/login
http://localhost:8000/api/v1/auth/dev/login?persona=athlete
http://localhost:8000/api/v1/auth/dev/login?persona=new_athlete
http://localhost:8000/api/v1/auth/dev/login?persona=admin
http://localhost:8000/api/v1/auth/dev/login?persona=super_admin
```

Each URL starts the normal OAuth login/callback path, seeds a throwaway local
user, sets the normal Playbook HttpOnly session cookie, and redirects to
`/chat`, `/profile`, or `/admin` on the frontend. See [Dev Auth](dev_auth.md)
for the concise reference.

Backend pytest runs do not load `backend/.env`. The test harness injects a
deterministic `Settings(_env_file=None, ...)` object with dev auth disabled, so
local no-SSO settings can remain in `.env` without changing test behavior.

The KB service signs status callbacks to
`http://localhost:8000/api/v1/kb/webhook` with `X-KB-Signature:
sha256=<hmac>`, where the HMAC secret is `KB_WEBHOOK_SECRET`.

## 4. Frontend

```bash
cd frontend

# Install dependencies
npm install

# Configure environment (point at the backend)
cp .env.local.example .env.local     # set NEXT_PUBLIC_API_URL=http://localhost:8000

# Run the dev server (http://localhost:3000)
npm run dev
```

The frontend routes are `/login`, `/profile`, `/chat`, `/admin`, and `/`.
The root route resolves the current session and redirects to the appropriate
Playbook surface.

## 5. KB Service

For standalone KB-service work, use Docker Compose for infrastructure and `uv`
for the API/workers:

```bash
# From the repo root: start Postgres, MinIO/S3, LiteLLM, and the KB broker.
docker compose -f deploy/compose/base.yml -f deploy/compose/local.yml up -d \
  db minio minio-bootstrap litellm kb-valkey

# Then run the KB API on the host with uv.
cd kb-service
uv sync
cp ../deploy/envs/.env.kb-service.local .env

# Host-run services need host ports instead of Docker service names in .env:
# DATABASE_URL=postgresql+asyncpg://app:localpass@localhost:5433/playbook
# CELERY_BROKER_URL=redis://localhost:6380/0
# CELERY_RESULT_BACKEND=redis://localhost:6380/1
# LITELLM_BASE_URL=http://localhost:4000
# S3_ENDPOINT_URL=http://localhost:9000
# APP_WEBHOOK_URL=http://localhost:8000

uv run alembic upgrade head
uv run uvicorn app.main:app --host 0.0.0.0 --port 8001
```

Run the KB ingest workers in separate terminals from `kb-service/`:

```bash
uv run celery -A app.workers.app worker -Q kb-cpu --pool=prefork --concurrency=2 --loglevel=info
uv run celery -A app.workers.app worker -Q kb-io,kb-notify --pool=threads --concurrency=50 --loglevel=info
```

For an all-Docker local stack, include the worker profile:

```bash
docker compose -f deploy/compose/base.yml -f deploy/compose/local.yml --profile worker up --build
```

KB infrastructure definitions:

| Component | Compose service | Local host port | Config |
|-----------|-----------------|-----------------|--------|
| Postgres + pgvector | `db` | `5433` | `deploy/compose/base.yml`, `deploy/compose/local.yml` |
| MinIO S3 API | `minio` | `9000` | `deploy/compose/local.yml` |
| MinIO bucket bootstrap | `minio-bootstrap` | n/a | creates `S3_BUCKET_NAME` (`playbook-bucket`) |
| KB broker/result backend | `kb-valkey` | `6380` | `deploy/compose/base.yml`, `deploy/compose/local.yml` |
| LiteLLM proxy | `litellm` | `4000` | `deploy/litellm/config.yaml`, `deploy/envs/.env.litellm.local` |
| KB API container | `kb-api` | `8001` | `deploy/compose/base.yml`, `deploy/compose/local.yml` |
| KB workers | `kb-worker-cpu`, `kb-worker-io` | n/a | enabled with `--profile worker` |

## 6. Verify End to End

1. Open http://localhost:3000.
2. Confirm the backend health check is reachable.
3. Confirm LiteLLM health is reachable on port `4000`.
4. Confirm Playbook migrations apply against the local `playbook` database.

## Common Issues

| Symptom | Fix |
|---------|-----|
| `uv` cannot find Python 3.12 | Run `uv python install 3.12` from the repo root |
| `connection refused` on DB | Ensure the Postgres container is running and `DATABASE_URL` matches the exposed port |
| `alembic` "target database is not up to date" | Run `alembic upgrade head` |
| LLM calls fail | Check LiteLLM health, `LLM_PROVIDER_MODE`, `LLM_CHAT_MODEL`, `LITELLM_BASE_URL`, and the LiteLLM service key in the app env. Provider API keys should be in `deploy/envs/.env.litellm.local` |
| Frontend can't reach API | Check `NEXT_PUBLIC_API_URL` and CORS settings on the backend |
