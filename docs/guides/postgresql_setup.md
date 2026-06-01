# Local PostgreSQL Setup

> Run Postgres locally for development. The Compose stack does this for you; this
> guide covers running it standalone and validating connectivity.

## Option A — Compose (recommended)

The `db` service is defined in `deploy/compose/base.yml` with local overrides in
`deploy/compose/local.yml` (exposed on host port `5433`):

```bash
docker compose -f deploy/compose/base.yml -f deploy/compose/local.yml up -d db
```

## Option B — Standalone container

```bash
docker run -d \
  --name app-postgres \
  -e POSTGRES_USER=app \
  -e POSTGRES_PASSWORD=localpass \
  -e POSTGRES_DB=appdb \
  -p 5433:5432 \
  -v app_pgdata:/var/lib/postgresql/data \
  postgres:16-alpine
```

## Connection String

For the backend `.env`:

```
DATABASE_URL=postgresql+asyncpg://app:localpass@localhost:5433/appdb
```

> Use the `+asyncpg` driver — the backend uses SQLAlchemy async sessions.

## Apply Migrations

```bash
cd backend
alembic upgrade head
```

## Validate

```bash
./deploy/scripts/validate-db.sh
```

This checks the container is running and healthy, the database exists, and
credentials work.

## Reset (destructive)

```bash
docker rm -f app-postgres
docker volume rm app_pgdata
```

Recreate with the run command above, then re-run `alembic upgrade head`.
