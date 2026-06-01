# Local Setup

> Get the backend and frontend running locally. Replace placeholder repo URLs
> and names with your own.

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.12+ | Backend (FastAPI) |
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
./deploy/scripts/deploy.sh local --build
```

Or start only the services you need — see
[postgresql_setup.md](postgresql_setup.md) and
[localstack_setup.md](localstack_setup.md).

## 3. Backend

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp ../deploy/envs/.env.local .env   # then edit values (e.g. ANTHROPIC_API_KEY)

# Apply database migrations
alembic upgrade head

# Run the dev server (http://localhost:8000)
uvicorn app.main:app --reload
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

## 5. Verify End to End

1. Open http://localhost:3000.
2. Register a user, log in.
3. Create an `Example` and confirm it lists.

## Common Issues

| Symptom | Fix |
|---------|-----|
| `connection refused` on DB | Ensure the Postgres container is running and `DATABASE_URL` matches the exposed port |
| `alembic` "target database is not up to date" | Run `alembic upgrade head` |
| LLM calls fail | Check `LLM_PROVIDER_MODE` and the relevant API key in `.env` |
| Frontend can't reach API | Check `NEXT_PUBLIC_API_URL` and CORS settings on the backend |
