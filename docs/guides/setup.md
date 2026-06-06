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
API keys (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`) belong in that LiteLLM-only env
file, not in backend or KB-service env files. For first local boot, the backend
and KB-service examples use `sk-local-litellm-master-key` as their LiteLLM
service key; after LiteLLM starts, generate a scoped key from
`http://localhost:4000/ui` and replace `LITELLM_API_KEY` /
`LLM_GATEWAY_API_KEY`.

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

Phase 1 auth and KB document control-plane settings:

```env
API_PUBLIC_URL=http://localhost:8000
OAUTH_STATE_SECRET=replace-with-a-long-random-value
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

The KB service signs status callbacks to
`http://localhost:8000/api/v1/kb/webhook` with `X-KB-Signature:
sha256=<hmac>`, where the HMAC secret is `KB_WEBHOOK_SECRET`.

## 4. Frontend

```bash
cd frontend

# Install dependencies
npm install

# Configure environment (point at the backend)
cp .env.example .env.local           # set NEXT_PUBLIC_API_URL=http://localhost:8000

# Run the dev server (http://localhost:3000)
npm run dev
```

## 5. KB Service

For standalone KB-service work:

```bash
cd kb-service
uv sync
uv run alembic upgrade head          # needs Postgres with pgvector
uv run python run_dev.py             # uvicorn on http://localhost:8001
```

If running KB-service directly on the host while LiteLLM runs in Docker, set
`LLM_GATEWAY_BASE_URL=http://localhost:4000` in `kb-service/.env`.

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
