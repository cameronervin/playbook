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
    ├── backup-db.sh
    ├── deploy.sh
    ├── generate-sbom.sh
    ├── load-test.sh
    ├── readiness-evidence.sh
    ├── release-validate.sh
    ├── restore-db.sh
    ├── security-scan.sh
    ├── validate-nginx.sh
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
./deploy/scripts/deploy.sh local|dev|prod [--build] [--down] [--logs] [--evidence]

# Examples
./deploy/scripts/deploy.sh local --build      # build images and start locally
./deploy/scripts/deploy.sh dev --logs         # start dev, follow logs
./deploy/scripts/deploy.sh prod --evidence    # start production and capture readiness evidence
./deploy/scripts/deploy.sh prod --down        # stop production
```

The script selects `deploy/envs/.env.<env>` automatically. For `prod` it
requires a real `.env.prod` (copy from `.env.prod.example`).

## Environment Differences

| Setting | Local | Dev | Prod |
|---------|-------|-----|------|
| DEBUG | true | true | false |
| LOG_LEVEL | DEBUG | DEBUG | WARNING |
| CELERY_WORKER_LOG_LEVEL | INFO | INFO | INFO |
| Dashboard insight schedule | Celery beat with `DASHBOARD_INSIGHTS_NIGHTLY_*` | same | same, one scheduler instance |
| Replicas | 1 | 1 | 3+ |
| Volumes | bind mounts (hot reload) | none | none |
| DB ports | exposed | exposed | internal only |
| Secrets | `.env` file | `.env` file | secrets manager |
| Agent stream Valkey URL | `redis://valkey:6379/2` | `redis://valkey:6379/2` | internal Valkey DB 2 |
| App rate limiting | Disabled by default | optional | `RATE_LIMIT_ENABLED=true`, shared Valkey DB 3 |
| Runtime tracing | Disabled unless `TRACING_ENABLED` and Langfuse env are set | optional approved Langfuse project | approved Langfuse project, secrets manager |
| Error monitoring | Disabled unless `SENTRY_ENABLED` and Sentry DSNs are set | optional approved Sentry projects | hosted Sentry projects for frontend, backend, and KB service |

## Production Notes

- **Secrets**: do not commit `.env.prod`. Use a secrets manager (AWS Secrets
  Manager, Vault, etc.) and inject values at deploy time.
- **Database**: do not expose the DB port; keep it on the internal network.
- **Health checks**: every service in `base.yml`/`prod.yml` defines a
  healthcheck — keep them.
- **Reverse proxy**: nginx terminates HTTPS, redirects HTTP to HTTPS, serves the
  frontend, and proxies `/api` to the backend (see `deploy/docker/nginx.conf`).
  Production certificates must be mounted or symlinked under
  `/etc/letsencrypt/live/playbook/`. Nginx access logs intentionally omit raw
  IPs, query strings, user agents, referrers, prompts, files, source text,
  signed URLs, tokens, and secrets.
- **LLM transport**: production should use `LLM_PROVIDER_MODE=litellm` and route
  backend, KB-service, and eval traffic through LiteLLM Proxy. Direct mode is
  reserved for local smoke tests or an explicit break-glass path.
- **Workers and beat**: run backend Celery workers for
  `backend-agent,backend-files,backend-insights,backend-maintenance` and run
  exactly one Celery beat scheduler instance. Beat schedules nightly dashboard
  insight runs; manual insight runs enqueue directly from the API.
- **Runtime tracing**: Langfuse tracing is off unless `TRACING_ENABLED=true`,
  `LANGFUSE_ENABLED=true`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and
  `LANGFUSE_BASE_URL` are provided to both the backend API and backend Celery
  workers. Treat `LANGFUSE_SECRET_KEY` as a secret-manager value. Do not inject
  Langfuse credentials into the frontend, KB-service, LiteLLM proxy, or reranker
  services unless those services gain their own approved tracing integration.
- **Error monitoring**: Sentry is off unless `SENTRY_ENABLED=true` and
  `SENTRY_DSN` are provided. Use hosted Sentry with separate projects for
  `frontend`, `backend`, and `kb-service`; backend workers share the backend
  DSN, and KB workers share the KB-service DSN. Runtime events are configured
  for errors and tracing only. Session Replay, user feedback, and Sentry Logs
  remain disabled. Scrubbers remove request bodies, cookies/auth headers,
  prompts, source text, signed URLs, tokens, raw IP fields, local variables, and
  Sentry user identity before events are sent.
- **Rate limiting**: production enables backend app-level sliding-window limits
  with `RATE_LIMIT_ENABLED=true`, `RATE_LIMIT_STORE_MODE=valkey`, and
  `RATE_LIMIT_VALKEY_URL` on a shared Valkey DB. These limits complement edge/WAF
  controls and LiteLLM virtual-key budgets; rate-limit logs include request,
  organization, and user IDs without prompts, files, tokens, secrets, or raw IPs.

## Sentry Monitoring

Use hosted Sentry SaaS for the initial rollout.

1. Create three Sentry projects: `frontend` for Next.js browser/server errors,
   `backend` for FastAPI plus backend Celery, and `kb-service` for KB FastAPI
   plus KB Celery.
2. Put the frontend public DSN in `NEXT_PUBLIC_SENTRY_DSN`. The DSN is public by
   design, but it should point only at the frontend project.
3. Put the backend project DSN in `deploy/envs/.env.backend.prod` as
   `SENTRY_DSN`. Put the KB project DSN in `deploy/envs/.env.kb-service.prod` as
   `SENTRY_DSN`. Both files are untracked runtime overlays copied from the
   committed `.example` templates.
4. Set `SENTRY_ENVIRONMENT=production`, set `SENTRY_RELEASE` to the release tag
   or commit SHA, and keep `SENTRY_TRACES_SAMPLE_RATE=0.1` at launch. Leave
   `SENTRY_PROFILES_SAMPLE_RATE=0.0` unless profiling is explicitly approved.
5. For frontend source-map upload, provide `SENTRY_AUTH_TOKEN`, `SENTRY_ORG`,
   and `SENTRY_PROJECT` only in CI/build scope. Local and PR builds must succeed
   without these values. Docker builds can pass the token as a BuildKit secret:

```bash
SENTRY_ORG=<org-slug> \
SENTRY_PROJECT=frontend \
NEXT_PUBLIC_SENTRY_DSN=<frontend-public-dsn> \
docker build \
  --secret id=sentry_auth_token,env=SENTRY_AUTH_TOKEN \
  --build-arg SENTRY_ORG \
  --build-arg SENTRY_PROJECT \
  --build-arg NEXT_PUBLIC_SENTRY_DSN \
  -f deploy/docker/Dockerfile.frontend frontend
```

Do not commit `SENTRY_AUTH_TOKEN`, do not add it to runtime env files, and do
not pass it as a normal Docker `ARG`.
Compose `build.args` are resolved from the shell or an explicit Compose
`--env-file`, not from a service `env_file`, so export `NEXT_PUBLIC_SENTRY_*`,
`SENTRY_ORG`, and `SENTRY_PROJECT` in the image-build environment when building
the production frontend image.

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
| Backend env | `LLM_PROVIDER_MODE=litellm`, `LITELLM_BASE_URL=http://litellm:4000`, `LITELLM_API_KEY=<service key>`, `LLM_CHAT_MODEL=playbook-chat`, and `CONVERSATION_FILE_MAX_UPLOAD_MB=200`; when runtime tracing is enabled, backend API and backend workers also receive `TRACING_ENABLED`, `LANGFUSE_ENABLED`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and `LANGFUSE_BASE_URL` |
| KB-service env | `LLM_PROVIDER_MODE=litellm`, `LITELLM_BASE_URL=http://litellm:4000`, `LITELLM_API_KEY=<service key>`, `LITELLM_EMBED_MODEL=playbook-embed`, `LITELLM_SUMMARY_MODEL=playbook-fast`, `LITELLM_RERANK_MODEL=playbook-rerank`; keep `KB_SEARCH_STRATEGY=semantic` and `KB_RERANK_ENABLED=false` by default, then enable `KB_SEARCH_STRATEGY=hybrid` plus `KB_RERANK_ENABLED=true` for reranked retrieval |
| LiteLLM env | Provider API keys, `LITELLM_MASTER_KEY`, `LITELLM_SALT_KEY`, `LITELLM_DATABASE_URL`, `LITELLM_PLAYBOOK_RERANK_MODEL`, `INFINITY_API_BASE`, and `INFINITY_API_KEY` |
| Reranker env | `INFINITY_API_KEY` and Infinity runtime settings only, copied from `deploy/envs/.env.reranker.example` to the environment-specific untracked file; do not include LiteLLM provider keys, master keys, or app service secrets |

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
and the `reranker` service, not by application runtimes. The reranker service
gets that token from a dedicated reranker env file instead of the LiteLLM env
file. Add other provider keys only when aliases use those providers. The
backend, KB-service, and eval runners should hold only scoped LiteLLM
virtual/service keys.

The project-owned LiteLLM image is defined in
`deploy/docker/Dockerfile.litellm` and uses `deploy/litellm/config.yaml` for
model aliases:

| Alias | Provider model | Used by |
|-------|----------------|---------|
| `playbook-chat` | `LITELLM_PLAYBOOK_CHAT_MODEL` | athlete chat, admin chat, eval judge default |
| `playbook-fast` | `LITELLM_PLAYBOOK_FAST_MODEL` | conversation titles, lightweight summaries, and fast agent paths |
| `playbook-embed` | `LITELLM_PLAYBOOK_EMBED_MODEL` | KB embeddings and retrieval evals |
| `playbook-ocr` | `LITELLM_PLAYBOOK_OCR_MODEL` | opt-in scanned PDF OCR when `OCR_PROVIDER=vlm` |
| `playbook-rerank` | `LITELLM_PLAYBOOK_RERANK_MODEL` | Infinity reranker alias for KB-service hybrid/rerank phases |

Create environment-specific LiteLLM virtual/service keys that follow the
non-secret policy manifest at
`backend/evals/release/litellm_virtual_key_policy.yaml`: backend, KB-service,
and eval keys have budget duration, `max_budget`, `rpm_limit`, and model
allowlists; the eval key is lower-budget for release/nightly runs and can access
`playbook-chat`, `playbook-fast`, and `playbook-embed`. The release checks
validate the manifest shape, while actual generated key values stay in LiteLLM
and the secrets manager.

The reranker container is enabled with the `reranker` profile. Local Compose
overrides the image to `michaelf34/infinity:0.0.75` for Apple Silicon ARM64
compatibility, serves `mixedbread-ai/mxbai-rerank-xsmall-v1` with the `torch`
engine, and disables local restart loops. Dev/prod keep the base
`BAAI/bge-reranker-base` plus `optimum` engine and explicit restart behavior
for managed environments:

```bash
cp deploy/envs/.env.reranker.example deploy/envs/.env.reranker.local
docker compose -f deploy/compose/base.yml -f deploy/compose/local.yml \
  --profile reranker up -d --build reranker litellm
```

If an old local `compose-reranker-1` container is repeatedly restarting after an
amd64/Rosetta startup failure, remove only that container after updating:

```bash
docker rm -f compose-reranker-1
```

Do not remove `compose_reranker_cache` unless switching local reranker models or
the reranker smoke fails with a cache/model artifact error.

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

# Nginx production config syntax with a throwaway test certificate
./deploy/scripts/validate-nginx.sh

# Compose health, nginx health, and backend/KB migration evidence
./deploy/scripts/readiness-evidence.sh prod

# Backend liveness and readiness
curl http://<host>/api/v1/health
curl http://<host>/api/v1/ready

# LiteLLM proxy health
curl http://<host-or-internal-litellm>:4000/health/liveliness
curl http://<host-or-internal-litellm>:4000/health/readiness

# Infinity reranker health, when the reranker profile is enabled
curl http://<host-or-internal-reranker>:7997/health

# KB-service rerank smoke, from an environment with KB-service env loaded
cd kb-service
uv run python scripts/smoke_kb_service.py --check-litellm-rerank

# Deterministic Phase 5 release validation from the repo root
cd ..
./deploy/scripts/release-validate.sh

# Full CI/release validation, including production build
./deploy/scripts/release-validate.sh --ci

# Include strict Langfuse-backed evals when credentials/services are available
./deploy/scripts/release-validate.sh --ci --live-evals

# Single-entry release validation with scanners and deployed staging smoke
STAGING_FRONTEND_URL=https://app.example.com \
STAGING_API_BASE_URL=https://app.example.com \
./deploy/scripts/release-validate.sh --ci --include-scanners --staging-smoke

# Staging Locust load gate, using pre-provisioned non-production test users
PLAYBOOK_ATHLETE_BEARER_TOKENS=<athlete-test-token> \
PLAYBOOK_ADMIN_BEARER_TOKENS=<admin-test-token> \
./deploy/scripts/load-test.sh staging \
  --profile smoke \
  --api-base-url https://staging.example.com

# Include the staging Locust smoke gate in the release wrapper
STAGING_FRONTEND_URL=https://staging.example.com \
STAGING_API_BASE_URL=https://staging.example.com \
PLAYBOOK_ATHLETE_BEARER_TOKENS=<athlete-test-token> \
PLAYBOOK_ADMIN_BEARER_TOKENS=<admin-test-token> \
./deploy/scripts/release-validate.sh --ci --staging-smoke --staging-load

# OSS AppSec scanner gate and CycloneDX SBOM artifacts
./deploy/scripts/security-scan.sh --skip-images
./deploy/scripts/generate-sbom.sh --skip-images

# Full local scanner/SBOM pass with Docker image builds
./deploy/scripts/security-scan.sh --build-images
./deploy/scripts/generate-sbom.sh --build-images

# Staging DAST runs from GitHub Actions
# .github/workflows/dast.yml -> workflow_dispatch with frontend_url and api_url

# Optional runtime tracing smoke, when Langfuse is enabled for backend + workers:
# confirm startup logs show ready=true, then trigger admin chat or dashboard
# insights and inspect the Langfuse trace for safe tags/ID metadata only.

# Optional Sentry smoke, when Sentry is enabled for staging/prod:
# trigger one synthetic unexpected 500 in an isolated staging path or task, then
# confirm the correct Sentry project receives the event and that request bodies,
# auth headers, prompts/source text, signed URLs, raw IPs, cookies, and user
# identity are absent.
```

GitHub Actions also runs `.github/workflows/security-scan.yml` on pull requests
and `.github/workflows/release-readiness.yml` on release tags/manual dispatch.
Scanner outputs and SBOMs are uploaded as workflow artifacts; keep committed
evidence to links and triage summaries as described in
`backstage/guides/security_scanning.md`.

## Load Testing

Locust load tests live in `load-tests/` as a separate `uv` project so Locust is
not installed into the backend runtime image. The default staging gate is cheap:
it exercises readiness, auth/session-protected current-user checks,
conversation lists, admin analytics reads, and KB document/catalog lists. Live
agent paths are opt-in with `--profile live-agent`; they enqueue chat/admin-chat
work by default and wait for SSE completion only when
`PLAYBOOK_LOAD_STREAM_MODE=wait`.

Load-test artifacts are written under `.artifacts/load-tests/<timestamp>/` and
include Locust HTML/CSV reports plus a sanitized `manifest.json`. Do not commit
these artifacts. Tokens, cookies, prompts, source text, signed URLs, and raw
response bodies are not written to the manifest.

Required staging inputs:

```bash
export STAGING_API_BASE_URL=https://staging.example.com
export PLAYBOOK_ATHLETE_BEARER_TOKENS=<comma-or-json-array>
export PLAYBOOK_ADMIN_BEARER_TOKENS=<comma-or-json-array>
```

Optional direct KB-service search inputs:

```bash
export STAGING_KB_BASE_URL=https://kb-staging.example.com
export PLAYBOOK_KB_API_SECRET=<service-token>
export PLAYBOOK_LOAD_ORGANIZATION_ID=<organization-uuid>
```

Common commands:

```bash
# Local command/argument smoke without opening sockets
./deploy/scripts/load-test.sh local --profile smoke --users 1 --spawn-rate 1 --run-time 30s --dry-run

# Staging cheap smoke gate
./deploy/scripts/load-test.sh staging --profile smoke --api-base-url "$STAGING_API_BASE_URL"

# Staging baseline once smoke is stable
./deploy/scripts/load-test.sh staging --profile baseline --api-base-url "$STAGING_API_BASE_URL"

# Budget-approved live agent enqueue test
PLAYBOOK_LOAD_STREAM_MODE=enqueue \
  ./deploy/scripts/load-test.sh staging --profile live-agent --api-base-url "$STAGING_API_BASE_URL"

# Explicit rate-limit probe, where 429 responses are expected
./deploy/scripts/load-test.sh staging --profile rate-limit --api-base-url "$STAGING_API_BASE_URL"
```

The script refuses production-like HTTPS targets by default. Use
`--allow-production-target` only for an explicitly approved production exercise
with a rollback owner and spend guardrails.

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

## Backup, Restore, and Migration Runbook

Use encrypted database dumps before production migrations and for restore
drills. The scripts require a passphrase from a secrets manager or a local
passphrase file; do not commit passphrases or generated backups.

```bash
# Create an encrypted custom-format dump and checksum.
BACKUP_PASSPHRASE_FILE=/secure/path/playbook-backup.pass \
  ./deploy/scripts/backup-db.sh prod --output-dir /secure/backups/playbook

# Restore into a drill database, not the primary DB.
BACKUP_PASSPHRASE_FILE=/secure/path/playbook-backup.pass \
  ./deploy/scripts/restore-db.sh prod \
    --backup-file /secure/backups/playbook/playbook-prod-db-<timestamp>.dump.enc \
    --target-db playbook_restore_drill

# Repeat a restore drill into the same drill DB.
BACKUP_PASSPHRASE_FILE=/secure/path/playbook-backup.pass \
  ./deploy/scripts/restore-db.sh prod \
    --backup-file /secure/backups/playbook/playbook-prod-db-<timestamp>.dump.enc \
    --target-db playbook_restore_drill \
    --overwrite
```

Before applying migrations, capture `./deploy/scripts/readiness-evidence.sh
prod`; after migrations, run it again and attach both logs to release evidence.
If a migration rollback is needed, restore the encrypted backup into a drill
database first, verify the app and KB Alembic heads/current state there, then
run the narrow `alembic downgrade` command only with release-owner approval.

Object storage recovery remains infrastructure-owned: production buckets should
enable encryption, retention/versioning, lifecycle policy, and access logging.
Record the bucket policy/versioning evidence next to the DB restore drill logs.
