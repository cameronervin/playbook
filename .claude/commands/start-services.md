
Start all required development services for local development.

## Services Started

1. **PostgreSQL** — container (`postgres-local`) on port 5432
2. **MinIO** — container (`minio`) on ports 9000/9001 — S3-compatible local storage
3. **Valkey** — container (`valkey-local`) on port 6379 — Celery broker / cache (optional)
4. **Backend** — FastAPI server (uvicorn) on http://127.0.0.1:8000
5. **Frontend** — Next.js dev server on http://localhost:3000
6. **Celery workers** — optional, one or more background-task workers

## Command Sequence

The agent should execute these steps in order. Examples use `docker`; substitute `podman` if that is your runtime.

### 1. Start Containers
```powershell
docker compose -f deploy/compose/base.yml -f deploy/compose/local.yml up -d db minio minio-bootstrap valkey
```

> If a container doesn't exist yet, create it once. Example for Valkey:
> ```powershell
> docker run -d --name valkey-local -p 6379:6379 valkey/valkey:7-alpine valkey-server --appendonly yes
> ```

### 2. Wait for Containers to be Healthy
```powershell
docker compose -f deploy/compose/base.yml -f deploy/compose/local.yml ps db minio valkey
```

### 3. Start Backend Server (in background)
```bash
# Working directory: backend/
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
# Run in background
```

### 4. Start Frontend Server (in background)
```bash
# Working directory: frontend/
npm run dev
# Run in background
```

### 5. Start Celery Workers (optional, in background)
```bash
# Working directory: backend/
celery -A app.workers.app:backend_worker worker -Q backend-agent,backend-files,backend-insights,backend-maintenance --concurrency=2 --loglevel=info
```

> Only needed if the project uses background tasks. The backend worker scaffold
> routes interactive agents, conversation files, dashboard insights, and
> maintenance tasks to named queues.

### 6. Verify All Services Running
- Backend: "Uvicorn running on http://127.0.0.1:8000"
- Frontend: "ready - started server on http://localhost:3000"
- Containers: `db`, `minio`, and `valkey` show "running"
- Celery workers (if started): each shows "ready"

## Service URLs
- Frontend: http://localhost:3000
- Backend API: http://127.0.0.1:8000
- API Docs: http://127.0.0.1:8000/docs
- PostgreSQL: localhost:5433
- MinIO API (S3-compatible): localhost:9000
- MinIO console: localhost:9001
- Valkey: localhost:6379

## Notes
- Use the tool's working-directory parameter instead of `cd`
- PowerShell doesn't support `&&` — chain with `;` or separate commands
- Backend and frontend should run in background
