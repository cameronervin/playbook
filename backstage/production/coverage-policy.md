# Risk-Based Coverage Policy

Last updated: July 2, 2026

## Policy

Playbook uses risk-based release coverage for production readiness. The release
gate does not require a single global coverage percentage. Instead, every
production-critical risk surface must have explicit tests and documentation
evidence.

`cd backend && uv run --group evals python -m evals.cli release-checks` validates
the machine-readable manifest in `backstage/production/coverage-policy.yaml`.
The check fails when a required surface is missing or when a referenced test/doc
file no longer exists.

## Required Surfaces

| Surface | Minimum evidence |
|---------|------------------|
| Auth | OAuth/session routes, auth dependencies, frontend auth API behavior. |
| Authz | Athlete/admin/super-admin route/API rejection and protected layouts. |
| Privacy/redaction | Backend, KB-service, admin analytics, Langfuse, and Sentry scrubbers. |
| Uploads | Direct-upload contracts, reconciliation, scoped conversation uploads, and frontend upload hooks. |
| KB ingest/search | Backend provider/outbox/webhook behavior and KB-service ingest/search workers. |
| Evals | Dataset validation, spec registration, runner behavior, deterministic judges, and release checks. |
| Admin analytics | Summary/query anonymization, dashboard insight generation, admin chat, and frontend analytics hooks. |
| Tracing/Sentry | Runtime tracing lifecycle and privacy-safe Sentry setup for frontend, backend, and KB-service. |
| Rate limits | Rate-limit service behavior plus route-level 429 gates for expensive paths. |

## Commands

```bash
cd backend && uv run pytest tests/unit/evals/test_release_checks.py -q
cd backend && uv run --group evals python -m evals.cli release-checks
./deploy/scripts/release-validate.sh
```

## Coverage Tooling Notes

Backend already has `pytest-cov` configuration in `backend/pyproject.toml`.
Frontend numeric coverage is intentionally not required in this P1 gate because
Vitest coverage would require adding a coverage provider package. Add frontend
coverage thresholds only after approving that dependency and calibrating
non-noisy thresholds.

## Evidence Hygiene

Store pointers to passing commands, workflow runs, and artifact names. Do not
store raw coverage HTML, raw SARIF/JSON, prompts, source text, signed URLs,
tokens, secrets, athlete identity, or raw IP addresses in committed evidence.
