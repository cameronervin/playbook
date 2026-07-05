# Local PostgreSQL Setup

> Run Postgres locally for development. The Compose stack does this for you; this
> guide covers running it standalone and validating connectivity.

## Option A — Compose (recommended)

The `db` service is defined in `deploy/compose/base.yml` with local overrides in
`deploy/compose/local.yml` (exposed on host port `5433`):

```bash
cp deploy/envs/.env.local.example deploy/envs/.env.local
docker compose -f deploy/compose/base.yml -f deploy/compose/local.yml up -d db
```

## Option B — Standalone container

```bash
docker run -d \
  --name app-postgres \
  -e POSTGRES_USER=app \
  -e POSTGRES_PASSWORD=localpass \
  -e POSTGRES_DB=playbook \
  -p 5433:5432 \
  -v app_pgdata:/var/lib/postgresql/data \
  postgres:16-alpine
```

## Connection String

For a backend running directly on your machine:

```
DATABASE_URL=postgresql+asyncpg://app:localpass@localhost:5433/playbook
```

For a backend running inside the Compose network, use the service hostname:

```
DATABASE_URL=postgresql+asyncpg://app:localpass@db:5432/playbook
```

> Use the `+asyncpg` driver — the backend uses SQLAlchemy async sessions.
> Host port `5433` maps to Postgres' default container port `5432`, avoiding
> conflicts with any Postgres server installed directly on your machine.

## Browser UI

Local Compose includes CloudBeaver CE for browsing schemas, editing data, and
running ad hoc SQL queries:

```bash
docker compose -f deploy/compose/base.yml -f deploy/compose/local.yml up -d db cloudbeaver
```

Open `http://localhost:5050` and log in with:

```
Username: playbook
Password: playbook-local-db-ui
```

Then create a PostgreSQL connection:

```
Host: db
Port: 5432
Database: playbook
Username: app
Password: localpass
```

Local Compose enables CloudBeaver custom connections so the new-connection
control is visible in the top toolbar.

If `5050` is already in use, set `DB_UI_PORT` in `deploy/envs/.env.local`
before starting the service. To change the local CloudBeaver admin password,
set `DB_UI_ADMIN_PASSWORD`.

## Apply Migrations

```bash
cd backend
alembic upgrade head
```

## Validate

```bash
./deploy/scripts/validate-db.sh
```

This checks the container is running, accepts connections to the configured
database, the database exists, and credentials work.

## Reset (destructive)

```bash
docker rm -f app-postgres
docker volume rm app_pgdata
```

Recreate with the run command above, then re-run `alembic upgrade head`.
