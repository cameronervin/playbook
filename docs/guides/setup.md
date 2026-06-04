# Local Setup

> Get the backend and frontend running locally. Replace placeholder repo URLs
> and names with your own.

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.12+ | Backend (FastAPI) |
| uv | latest | Python package and environment manager |
| Node.js | 20+ | Frontend (Next.js) |
| Docker | latest | Postgres, LocalStack, Valkey |
| Git | latest | — |

## 1. Clone

```bash
git clone <your-repo-url> agentic-app
cd agentic-app
```

## 2. Start Infrastructure

Start Postgres (and optionally LocalStack + Valkey) via Docker Compose:

```bash
cp deploy/envs/.env.local.example deploy/envs/.env.local
./deploy/scripts/deploy.sh local --build
```

Or start only the services you need — see
[postgresql_setup.md](postgresql_setup.md) and
[localstack_setup.md](localstack_setup.md).

## 3. Backend

```bash
cd backend

# Install Python 3.12 if needed, then create/sync the managed environment
uv python install 3.12
uv sync

# Configure environment
cp ../deploy/envs/.env.local .env   # then edit values (e.g. ANTHROPIC_API_KEY)

# Apply database migrations
uv run alembic upgrade head

# Run the dev server (http://localhost:8000)
uv run uvicorn app.main:app --reload
```

Verify: `curl http://localhost:8000/api/v1/health` → `{"status": "ok"}`.

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

## 6. Verify End to End

1. Open http://localhost:3000.
2. Confirm the backend health check is reachable.
3. Confirm Playbook migrations apply against the local `playbook` database.

## Common Issues

| Symptom | Fix |
|---------|-----|
| `uv` cannot find Python 3.12 | Run `uv python install 3.12` from the repo root |
| `connection refused` on DB | Ensure the Postgres container is running and `DATABASE_URL` matches the exposed port |
| `alembic` "target database is not up to date" | Run `alembic upgrade head` |
| LLM calls fail | Check `LLM_PROVIDER_MODE` and the relevant API key in `.env` |
| Frontend can't reach API | Check `NEXT_PUBLIC_API_URL` and CORS settings on the backend |
