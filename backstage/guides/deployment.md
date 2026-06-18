# Deployment

> Deploy with Docker Compose using a shared base file plus per-environment
> overrides. Adjust replica counts, resource limits, and secret sources to your
> infrastructure.

## Compose Structure

```
deploy/
├── compose/
│   ├── base.yml      # Shared service definitions (db, backend, frontend, valkey, ...)
│   ├── local.yml     # Local dev: bind mounts, hot reload, exposed ports, MinIO
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

Python service images use `uv sync --locked --no-dev` against each service's
committed `pyproject.toml` and `uv.lock`. The container virtual environment is
created at `/opt/venv`, which keeps local bind mounts from hiding installed
packages during hot-reload development.

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
| Agent stream Valkey URL | `redis://valkey:6379/2` | `redis://valkey:6379/2` | internal Valkey DB 2 |

## Production Notes

- **Secrets**: do not commit `.env.prod`. Use a secrets manager (AWS Secrets
  Manager, Vault, etc.) and inject values at deploy time.
- **Database**: do not expose the DB port; keep it on the internal network.
- **Health checks**: every service in `base.yml`/`prod.yml` defines a
  healthcheck — keep them.
- **Reverse proxy**: nginx serves the frontend and proxies `/api` to the
  backend (see `deploy/docker/nginx.conf`).
- **LLM transport**: production should use `LLM_PROVIDER_MODE=litellm` and route
  backend, KB-service, and eval traffic through LiteLLM Proxy. Direct mode is
  reserved for local smoke tests or an explicit break-glass path.

## LiteLLM Proxy

LiteLLM should run as its own service/container in deployed environments. The
application services should not hold provider API keys directly; they should
call the proxy with `LITELLM_BASE_URL` and a LiteLLM virtual/service key.

Recommended deployment shape:

| Component | Responsibility |
|-----------|----------------|
| `litellm` service | Runs LiteLLM Proxy on the internal network, usually port `4000` |
| `reranker` service | Optional Infinity reranker profile on the internal network, port `7997` |
| LiteLLM config file | Defines model aliases such as `playbook-chat`, `playbook-fast`, `playbook-embed`, optional `playbook-ocr`, and `playbook-rerank` |
| LiteLLM database | Stores LiteLLM-managed virtual keys, model config, spend, budgets, and audit metadata |
| Backend env | `LLM_PROVIDER_MODE=litellm`, `LITELLM_BASE_URL=http://litellm:4000`, `LITELLM_API_KEY=<service key>`, `LLM_CHAT_MODEL=playbook-chat`, and `CONVERSATION_FILE_MAX_UPLOAD_MB=200` |
| KB-service env | `LLM_PROVIDER_MODE=litellm`, `LITELLM_BASE_URL=http://litellm:4000`, `LITELLM_API_KEY=<service key>`, `LITELLM_EMBED_MODEL=playbook-embed`, `LITELLM_SUMMARY_MODEL=playbook-fast`, `LITELLM_RERANK_MODEL=playbook-rerank`; keep `KB_SEARCH_STRATEGY=semantic` and `KB_RERANK_ENABLED=false` by default, then enable `KB_SEARCH_STRATEGY=hybrid` plus `KB_RERANK_ENABLED=true` for reranked retrieval |
| LiteLLM env | Provider API keys, `LITELLM_MASTER_KEY`, `LITELLM_SALT_KEY`, `LITELLM_DATABASE_URL`, `LITELLM_PLAYBOOK_RERANK_MODEL`, `INFINITY_API_BASE`, and `INFINITY_API_KEY` |

Use a separate LiteLLM database or at least a separate database/user in the
Postgres cluster. Do not add LiteLLM tables to the Playbook application data
model or manage them with Playbook Alembic migrations; LiteLLM owns its own
schema and migrations.

LiteLLM's database is optional for a minimal proxy, but it is required for the
features Playbook wants in scope: virtual keys, spend tracking, budgets, and the
admin UI. That means the production deployment should include a LiteLLM DB
connection and stable `LITELLM_MASTER_KEY`/`LITELLM_SALT_KEY` secrets.
Provider API keys such as `OPENAI_API_KEY` should be available only to the
LiteLLM proxy service. `INFINITY_API_KEY` is an internal token shared by LiteLLM
and the `reranker` service, not by application runtimes. Add other provider keys
only when aliases use those providers. The backend and KB-service should hold
only LiteLLM virtual/service keys.

The project-owned LiteLLM image is defined in
`deploy/docker/Dockerfile.litellm` and uses `deploy/litellm/config.yaml` for
model aliases:

| Alias | Provider model | Used by |
|-------|----------------|---------|
| `playbook-chat` | `LITELLM_PLAYBOOK_CHAT_MODEL` | athlete chat, admin chat, eval judge default |
| `playbook-fast` | `LITELLM_PLAYBOOK_FAST_MODEL` | lightweight summaries and fast agent paths |
| `playbook-embed` | `LITELLM_PLAYBOOK_EMBED_MODEL` | KB embeddings and retrieval evals |
| `playbook-ocr` | `LITELLM_PLAYBOOK_OCR_MODEL` | opt-in scanned PDF OCR when `OCR_PROVIDER=vlm` |
| `playbook-rerank` | `LITELLM_PLAYBOOK_RERANK_MODEL` | Infinity reranker alias for KB-service hybrid/rerank phases |

The reranker container is enabled with the `reranker` profile and uses
`michaelf34/infinity:latest-cpu` by default:

```bash
docker compose -f deploy/compose/base.yml -f deploy/compose/local.yml \
  --profile reranker up -d --build reranker litellm
```

This configures model serving and LiteLLM routing. KB-service uses semantic
pgvector retrieval by default; reranked retrieval requires
`KB_SEARCH_STRATEGY=hybrid`, `KB_RERANK_ENABLED=true`, and a KB-service LiteLLM
virtual key that can call `playbook-rerank`.

For local Compose, `litellm-db-init` creates a separate `litellm` database in
the local Postgres container. Production should provision the LiteLLM database
through infrastructure or a managed database workflow and provide
`LITELLM_DATABASE_URL` through the secrets manager.

See [Self-Hosted LiteLLM](litellm_self_hosting.md) for the concise operations
guide.

## Verifying a Deploy

```bash
# Database readiness
./deploy/scripts/validate-db.sh

# Backend health
curl http://<host>/api/v1/health

# LiteLLM proxy health
curl http://<host-or-internal-litellm>:4000/health/liveliness
curl http://<host-or-internal-litellm>:4000/health/readiness

# Infinity reranker health, when the reranker profile is enabled
curl http://<host-or-internal-reranker>:7997/health

# KB-service rerank smoke, from an environment with KB-service env loaded
cd kb-service
uv run python scripts/smoke_kb_service.py --check-litellm-rerank
```

For a reranker outage drill, keep `KB_SEARCH_STRATEGY=hybrid`,
`KB_RERANK_ENABLED=true`, and `KB_RERANK_FAIL_OPEN=true`, temporarily stop or
misroute the reranker, and run `uv run python scripts/smoke_kb_service.py
--expect-rerank-fail-open`. Passing output proves KB-service preserved hybrid
ordering instead of failing chat retrieval outright.

To verify Python dependency resolution before a deploy:

```bash
cd backend && uv sync --locked
cd ../kb-service && uv sync --locked
```
