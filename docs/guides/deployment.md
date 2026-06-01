# Deployment

> Deploy with Docker Compose using a shared base file plus per-environment
> overrides. Adjust replica counts, resource limits, and secret sources to your
> infrastructure.

## Compose Structure

```
deploy/
├── compose/
│   ├── base.yml      # Shared service definitions (db, backend, frontend, valkey, ...)
│   ├── local.yml     # Local dev: bind mounts, hot reload, exposed ports, LocalStack
│   ├── dev.yml       # Dev server: built images, exposed API
│   └── prod.yml      # Production: no volumes, replicas, internal DB, resource limits
├── docker/
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   └── nginx.conf
├── envs/
│   ├── .env.local
│   ├── .env.dev
│   └── .env.prod.example   # copy to .env.prod with real values (never committed)
└── scripts/
    ├── deploy.sh
    └── validate-db.sh
```

Compose pattern: `base.yml` defines services; each `<env>.yml` overrides only
what differs.

```bash
docker compose -f deploy/compose/base.yml -f deploy/compose/local.yml up
```

## Deploy Script

`deploy/scripts/deploy.sh` wraps the compose invocation:

```bash
# Usage
./deploy/scripts/deploy.sh local|dev|prod [--build] [--down] [--logs]

# Examples
./deploy/scripts/deploy.sh local --build      # build images and start locally
./deploy/scripts/deploy.sh dev --logs         # start dev, follow logs
./deploy/scripts/deploy.sh prod               # start production (detached)
./deploy/scripts/deploy.sh prod --down        # stop production
```

The script selects `deploy/envs/.env.<env>` automatically. For `prod` it
requires a real `.env.prod` (copy from `.env.prod.example`).

## Environment Differences

| Setting | Local | Dev | Prod |
|---------|-------|-----|------|
| DEBUG | true | true | false |
| LOG_LEVEL | DEBUG | DEBUG | WARNING |
| Replicas | 1 | 1 | 3+ |
| Volumes | bind mounts (hot reload) | none | none |
| DB ports | exposed | exposed | internal only |
| Secrets | `.env` file | `.env` file | secrets manager |

## Production Notes

- **Secrets**: do not commit `.env.prod`. Use a secrets manager (AWS Secrets
  Manager, Vault, etc.) and inject values at deploy time.
- **Database**: do not expose the DB port; keep it on the internal network.
- **Health checks**: every service in `base.yml`/`prod.yml` defines a
  healthcheck — keep them.
- **Reverse proxy**: nginx serves the frontend and proxies `/api` to the
  backend (see `deploy/docker/nginx.conf`).
- **LLM transport**: set `LLM_PROVIDER_MODE` (`direct` or `gateway`) and the
  matching credentials per environment.

## Verifying a Deploy

```bash
# Database readiness
./deploy/scripts/validate-db.sh

# Backend health
curl http://<host>/api/v1/health
```
