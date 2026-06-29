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

The self-hosted Infinity reranker is optional during normal local boot. Start it
when validating LiteLLM `/rerank` routing:

```bash
cp deploy/envs/.env.reranker.example deploy/envs/.env.reranker.local
docker compose -f deploy/compose/base.yml -f deploy/compose/local.yml \
  --profile reranker up -d --build reranker litellm

curl http://localhost:7997/health
```

On Apple Silicon, the local reranker override uses
`michaelf34/infinity:0.0.75`, which has a `linux/arm64` manifest, and serves
`mixedbread-ai/mxbai-rerank-xsmall-v1` with Infinity's `torch` engine. Dev and
prod keep the base `BAAI/bge-reranker-base` target. Local reranker restart is
disabled so a bad model startup does not keep relaunching. If an older reranker
container is already looping, run `docker rm -f compose-reranker-1` after
updating the config; remove `compose_reranker_cache` only when switching model
artifacts or when the smoke test reports cache/model artifact problems.

Then smoke the LiteLLM rerank alias:

```bash
source deploy/envs/.env.litellm.local

curl -s -X POST "http://localhost:4000/rerank" \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "playbook-rerank",
    "query": "What must an athlete do before signing a NIL deal?",
    "documents": [
      "Athletes must disclose NIL agreements before signing.",
      "Travel reimbursement forms are due after road games.",
      "Equipment checkout happens at the start of each season."
    ],
    "top_n": 2
  }'
```

`playbook-rerank` is configured for KB-service hybrid/rerank phases, and the
KB-service has an internal LiteLLM `/rerank` provider. Search remains
semantic-only while `KB_SEARCH_STRATEGY=semantic`; hybrid reranking requires
`KB_SEARCH_STRATEGY=hybrid` and `KB_RERANK_ENABLED=true`.

Then smoke the LiteLLM summary/chat alias when validating KB source-summary
generation:

```bash
source deploy/envs/.env.litellm.local

curl -s -X POST "http://localhost:4000/chat/completions" \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "playbook-fast",
    "messages": [
      {"role": "system", "content": "Reply with exactly ok."},
      {"role": "user", "content": "LiteLLM summary alias health check."}
    ],
    "temperature": 0,
    "max_tokens": 8
  }'
```

The KB runtime keeps extractive summary fallback enabled, but this preflight
detects a bad `playbook-fast` alias or LiteLLM key before ingestion tests rely on
fallback behavior.

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
# S3_ENDPOINT_URL=http://localhost:9000
# S3_PUBLIC_ENDPOINT_URL=http://localhost:9000

# Apply database migrations
uv run alembic upgrade head

# Run the dev server (http://localhost:8000)
uv run uvicorn app.main:app --reload
```

If a host shell exports a non-boolean `DEBUG` value, prefix host-run backend
commands with `DEBUG=true` or `DEBUG=false` so pydantic-settings parses the
environment consistently.

Verify: `curl http://localhost:8000/api/v1/health` → `{"status": "healthy"}`.

Optional backend worker for Phase 2+ async jobs. Keep both `backend-files` and
`backend-maintenance` in the queue list so verified direct uploads dispatch to
KB-service and scheduled passes reconcile expired direct-upload intents:

```bash
uv run celery -A app.workers.app:backend_worker worker -Q backend-agent,backend-files,backend-insights,backend-maintenance --concurrency=2 --loglevel=info
```

Backend workers use `CELERY_WORKER_LOG_LEVEL` independently from API
`LOG_LEVEL`, so local API logs can stay at `DEBUG` while worker logs default to
`INFO`. Restart any already-running worker after changing this value. If old
delayed maintenance tasks are already queued in local Valkey, they may still run
once; purging a queue is destructive and should only be done when you are sure no
needed local tasks are pending.

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
Developer SSO provider on the login screen. It opens a role menu for athlete,
new-athlete, admin, and super-admin browser sessions. Each option starts the
normal OAuth login/callback path, seeds a throwaway local user, sets the normal
Playbook HttpOnly session cookie, and redirects to `/chat`, `/profile`, or
`/admin` on the frontend. See [Dev Auth](dev_auth.md) for the concise
reference.

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
# CONVERSATION_FILE_MAX_UPLOAD_MB=200
# APP_WEBHOOK_URL=http://localhost:8000
# KB_SEARCH_STRATEGY=semantic
# KB_RERANK_ENABLED=false
# LOG_LEVEL=INFO

uv run alembic upgrade head
uv run uvicorn app.main:app --host 0.0.0.0 --port 8001
```

KB-service logging redacts structlog and stdlib records before rendering and
keeps noisy SDK loggers above DEBUG by default. Prefer worker `--loglevel=info`
for normal local smoke tests; temporarily raising app `LOG_LEVEL=DEBUG` should
not emit LiteLLM prompts, source excerpts, or S3 signing details from the common
SDK loggers.

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
| CloudBeaver DB UI | `cloudbeaver` | `5050` | `deploy/compose/local.yml`, `deploy/envs/.env.local` |
| MinIO S3 API | `minio` | `9000` | `deploy/compose/local.yml` |
| MinIO bucket bootstrap | `minio-bootstrap` | n/a | creates `S3_BUCKET_NAME` (`playbook-bucket`) |
| KB broker/result backend | `kb-valkey` | `6380` | `deploy/compose/base.yml`, `deploy/compose/local.yml` |
| LiteLLM proxy | `litellm` | `4000` | `deploy/litellm/config.yaml`, `deploy/envs/.env.litellm.local` |
| Infinity reranker | `reranker` | `7997` | enabled with `--profile reranker`, env in `deploy/envs/.env.reranker.local` copied from `deploy/envs/.env.reranker.example` |
| KB API container | `kb-api` | `8001` | `deploy/compose/base.yml`, `deploy/compose/local.yml` |
| KB workers | `kb-worker-cpu`, `kb-worker-io` | n/a | enabled with `--profile worker` |

## 6. Verify End to End

1. Open http://localhost:3000.
2. Confirm the backend health check is reachable.
3. Confirm LiteLLM health is reachable on port `4000`.
4. If rerank routing is in scope, confirm the `reranker` health endpoint is
   reachable on port `7997` and the LiteLLM `/rerank` smoke returns ranked
   `results`.
5. Confirm Playbook migrations apply against the local `playbook` database.
6. From `kb-service/`, run `uv run alembic upgrade head` so the live KB schema
   matches the current models. For the Phase 3 semantic retrieval path, run the
   KB API and workers with `KB_SEARCH_STRATEGY=semantic` and
   `KB_RERANK_ENABLED=false`, then run `uv run python
   scripts/smoke_kb_service.py --include-conversation-file` for shared
   ingest/search, private conversation-file isolation, and post-delete
   original/staging cleanup assertions. Add `--check-litellm-summary` when
   validating the `playbook-fast` LiteLLM summary alias. Hybrid rerank can be
   smoked separately with `--check-litellm-rerank` once the local reranker alias
   is in scope.

### Direct Upload Smoke

Before validating admin or athlete uploads through the browser, confirm these
processes are running:

- MinIO plus `minio-bootstrap`, with browser preflight from
  `http://localhost:3000` allowing direct-upload POST requests.
- Backend API on `http://localhost:8000`.
- Backend worker listening on `backend-files` and `backend-maintenance`.
- KB-service API on `http://localhost:8001`.
- KB-service CPU and IO/notify workers.
- Frontend on `http://localhost:3000`.

Then smoke the implemented browser path:

1. Sign in locally as an admin and upload a supported KB document from
   `/admin`. Confirm the row moves from local upload progress to
   `upload_pending`, `uploaded`/queued, `processing`, and then `ready` or a safe
   `failed` reason.
2. Sign in locally as an athlete, open `/chat`, attach a supported file to an
   existing conversation or queue it before the first message creates a
   conversation. Confirm the file moves through `upload_pending`, `uploaded` or
   `extracting`, and then `ready` or a safe `failed` reason.
3. Re-run the KB-service smoke with private source coverage:

   ```bash
   cd kb-service
   export KB_SEARCH_STRATEGY=semantic
   export KB_RERANK_ENABLED=false
   uv run python scripts/smoke_kb_service.py --include-conversation-file
   ```

   Add `--check-litellm-summary` to the smoke command after confirming the
   LiteLLM `playbook-fast` alias is reachable; leave it off when intentionally
   validating the extractive fallback path.

4. Run the Phase 3 backend-to-KB smoke. It seeds local admin/athlete tokens,
   performs a direct KB upload, waits for webhook-mirrored ready status, verifies
   `LocalKBProvider` search, streams an athlete chat answer, checks persisted
   citation metadata, proves malformed documents stay out of retrieval, retries
   the linked document, and deletes the smoke data:

   ```bash
   cd backend
   uv run python scripts/phase3_kb_e2e_smoke.py \
     --backend-url http://localhost:8000 \
     --kb-url http://localhost:8001 \
     --timeout-seconds 300
   ```

5. If seeded local retrieval data is available, ask a question that should use a
   ready conversation file and confirm the answer cites that file.

## Common Issues

| Symptom | Fix |
|---------|-----|
| `uv` cannot find Python 3.12 | Run `uv python install 3.12` from the repo root |
| `connection refused` on DB | Ensure the Postgres container is running and `DATABASE_URL` matches the exposed port |
| `alembic` "target database is not up to date" | Run `alembic upgrade head` |
| LLM calls fail | Check LiteLLM health, `LLM_PROVIDER_MODE`, `LLM_CHAT_MODEL`, `LITELLM_BASE_URL`, and the LiteLLM service key in the app env. Provider API keys should be in `deploy/envs/.env.litellm.local` |
| Frontend can't reach API | Check `NEXT_PUBLIC_API_URL` and CORS settings on the backend |
