# Production Readiness Playbook

Use this as the agent checklist for moving Playbook from prototype to real
users. Keep it concise. Add details only when they become executable commands,
tests, docs, or runbooks.

## Rule For Agents

- Do not mark an item done without evidence: command output, test name, linked doc, or smoke result.
- Keep all production secrets out of git. Use placeholders in committed files.
- Preserve privacy defaults: no prompts, files, source text, signed URLs, tokens, secrets, raw IP addresses, or athlete identity in logs/traces.
- Update this file and `phase-5-evaluation-and-release-readiness.md` when a gate is implemented or intentionally deferred.

## P0 Gates Before Real Users

- [x] **CI release command** runs backend, frontend, KB-service, evals, scanners, and smoke checks with a single documented entrypoint. Evidence: `deploy/scripts/release-validate.sh --ci --include-scanners --staging-smoke`, `.github/workflows/release-readiness.yml`.
- [x] **SAST** runs on every PR for Python and TypeScript. Minimum baseline: Semgrep plus Bandit for Python-sensitive paths. Evidence: `.github/workflows/security-scan.yml`, `.semgrep.yml`, `deploy/scripts/security-scan.sh`.
- [x] **OSS/SCA** runs on every PR and release. Minimum baseline: `pip-audit`, OSV-Scanner, `npm audit`, and lockfile verification. Evidence: `.github/workflows/security-scan.yml`, `.github/workflows/release-readiness.yml`, `deploy/scripts/security-scan.sh`.
- [x] **Secrets scanning** runs on PRs and full history before launch. Minimum baseline: Gitleaks or equivalent. Evidence: `.gitleaks.toml`, `.github/workflows/security-scan.yml` with full-history checkout.
- [x] **Container/IaC scanning** runs for production images and deploy files. Minimum baseline: Trivy or equivalent. Evidence: `deploy/scripts/security-scan.sh --build-images`, `.github/workflows/security-scan.yml`.
- [x] **DAST** runs against staging. Minimum baseline: OWASP ZAP scan for frontend and `/api/v1`. Evidence: `.github/workflows/dast.yml` manual dispatch with `frontend_url` and `api_url`, artifact `dast-artifacts`.
- [x] **SBOM** is generated and stored for each release: backend, frontend, KB-service, and container images. Evidence: `deploy/scripts/generate-sbom.sh`, `.github/workflows/release-readiness.yml`, `backstage/guides/security_scanning.md`.
- [ ] **Load testing** runs against staging before production. Minimum baseline: Locust smoke/baseline profiles for readiness, auth, athlete/admin read paths, and opt-in live agent/SSE paths when LLM budget is approved. Evidence hook: `deploy/scripts/load-test.sh`, `deploy/scripts/release-validate.sh --staging-load`, artifact `load-test-artifacts`; keep open until staging artifacts are attached.
- [ ] **Auth/authz checks** prove unauthenticated users cannot access app routes, athletes cannot access admin APIs, admins cannot perform super-admin actions, and KB-service auth rejects bad service tokens.
- [x] **Rate limits and abuse controls** cover auth callbacks, chat/admin chat, manual insight runs, uploads, list endpoints, and expensive LLM/embedding/rerank paths.
- [ ] **Privacy checks** prove admin analytics stays anonymized and logs/traces exclude secrets, prompts, source text, signed URLs, tokens, raw IP addresses, and athlete identity.
- [ ] **LLM gateway controls** prove production uses LiteLLM aliases, provider keys stay out of app services, and virtual keys have per-environment budgets/rate limits.
- [ ] **Eval gates** pass for retrieval, citations, grounded answers, refusals, emergency handling, admin insights, admin chat, and conversation titles.
- [ ] **Deployment hardening** includes HTTPS, explicit CORS, security headers, request/body limits, internal DB/Valkey access only, health checks, resource limits, and non-debug prod config.
- [X] **Backups and recovery** include encrypted DB backups, object-storage retention/versioning, restore drill, migration rollback path, and documented RPO/RTO.
- [x] **Cookie posture** uses only essential cookies by default. Do not add analytics, marketing, replay, ad, or cross-site tracking cookies unless a separate consent/preference flow is implemented first.
- [x] **Privacy/legal artifacts** exist: privacy notice, terms/acceptable use, essential-cookie notice, subprocessor list, data retention/deletion policy, vulnerability disclosure path, and incident contact. Starter terms draft: `_terms-and-conditions.md`.

## P1 Gates Before Institutional Rollout

- [ ] **Coverage policy** is risk-based: auth, authz, privacy, upload, KB ingest/search, eval, admin analytics, tracing, and rate-limit paths have explicit tests.
- [ ] **Operational monitoring** covers API errors, auth failures, rate-limit events, worker backlog, KB ingest failures, retrieval no-result rate, LLM spend/latency, and storage failures. Sentry errors/tracing are wired for frontend, backend, backend workers, KB API, and KB workers with privacy scrubbers; keep this open until staging/prod projects, alerts, and smoke evidence are attached.
- [ ] **Incident runbook** defines severity levels, owner, communication path, containment, secret rotation, evidence capture, and post-incident review.
- [X] **Access reviews** cover OAuth apps, cloud/IAM roles, database users, LiteLLM keys, Langfuse access, S3 buckets, and admin/super-admin users.
- [ ] **Data lifecycle** documents retention, deletion, export, audit-log retention, eval dataset redaction, and production-to-test data rules.
- [X] **Cookie inventory** is reviewed before each institutional rollout and confirms only auth/session, OAuth state, CSRF/security, and service-protection cookies or equivalent essential storage.
- [ ] **Pen test or external review** is scheduled after P0 automation is green.

## Required Command Set

Document or implement these commands before marking the release gate done:

```bash
# Backend
cd backend && uv run pytest -v
cd backend && uv run ruff check app tests
cd backend && uv run --group evals python -m evals.cli validate-datasets
cd backend && uv run --group evals python -m evals.cli run-all --strict --max-concurrency 5

# KB service
cd kb-service && uv run pytest -v
cd kb-service && uv run ruff check app tests
cd kb-service && uv run python scripts/smoke_kb_service.py --check-litellm-summary

# Frontend
cd frontend && npm test
cd frontend && npm run typecheck
cd frontend && npm run lint
cd frontend && npm run build

# Deploy smoke
./deploy/scripts/validate-db.sh
./deploy/scripts/validate-nginx.sh
./deploy/scripts/readiness-evidence.sh prod
curl -f http://<host>/api/v1/health
curl -f http://<host>/api/v1/ready
curl -f http://<internal-litellm>:4000/health/readiness

# Staging load gate
./deploy/scripts/load-test.sh staging --profile smoke --api-base-url https://staging.example.com
STAGING_API_BASE_URL=https://staging.example.com ./deploy/scripts/release-validate.sh --ci --staging-smoke --staging-load

# Backup / restore drill evidence
BACKUP_PASSPHRASE_FILE=/secure/path/playbook-backup.pass ./deploy/scripts/backup-db.sh prod --output-dir /secure/backups/playbook
BACKUP_PASSPHRASE_FILE=/secure/path/playbook-backup.pass ./deploy/scripts/restore-db.sh prod --backup-file /secure/backups/playbook/<backup>.dump.enc --target-db playbook_restore_drill
```

Deployment hardening evidence hooks now live in
`deploy/scripts/validate-nginx.sh` and `deploy/scripts/readiness-evidence.sh`.
Recovery evidence hooks now live in `deploy/scripts/backup-db.sh` and
`deploy/scripts/restore-db.sh`. Keep the P0 deployment and recovery gates open
until these commands pass against the real staging/production environment and
object-storage encryption/versioning/retention evidence is attached.

## Scanner Baseline

Implement equivalent CI jobs if tool names change:

- SAST: Semgrep CE and Bandit via `deploy/scripts/security-scan.sh`.
- OSS/SCA: `pip-audit`, OSV-Scanner, `npm audit`, and lockfile verification via GitHub Actions.
- Secrets: Gitleaks with redacted SARIF output and full-history checkout.
- Containers/IaC/SBOM: Trivy filesystem/config/image scans plus CycloneDX JSON SBOM artifacts.
- DAST: OWASP ZAP against staging.

## Done Means

- All P0 gates are green.
- No critical or high vulnerabilities are untriaged.
- Any accepted risk has owner, expiry date, mitigation, and rollback path.
- Evidence is linked from `phase-5-evaluation-and-release-readiness.md` or the release notes.
