#!/usr/bin/env bash
# Phase 5 release validation wrapper.
#
# Default mode runs deterministic checks that should be suitable for local
# pre-release validation and CI. Use --live-evals only when Langfuse, LiteLLM,
# and KB-service credentials/services are intentionally available.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUN_FRONTEND=true
RUN_KB=true
RUN_LIVE_EVALS=false

usage() {
    cat <<'USAGE'
Usage: ./deploy/scripts/release-validate.sh [options]

Options:
  --live-evals       Also run Langfuse-backed evals with strict thresholds.
  --skip-frontend    Skip frontend lint, typecheck, and tests.
  --skip-kb          Skip KB-service contract/redaction tests.
  -h, --help         Show this help.
USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --live-evals)
            RUN_LIVE_EVALS=true
            ;;
        --skip-frontend)
            RUN_FRONTEND=false
            ;;
        --skip-kb)
            RUN_KB=false
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
    shift
done

run_step() {
    local label="$1"
    shift

    echo
    echo "==> ${label}"
    "$@"
}

run_step "backend unit, eval, logging, auth, and rate-limit tests" \
    bash -c "cd '$ROOT_DIR/backend' && uv run pytest \
        tests/unit/test_rate_limit_service.py \
        tests/unit/evals \
        tests/unit/test_logging_config.py \
        tests/unit/test_log_redaction.py \
        tests/unit/test_langfuse_init.py \
        tests/unit/test_agent_trace.py \
        tests/unit/test_auth_dependencies.py \
        -q"

run_step "backend security/audit/rate-limit integration slice" \
    bash -c "cd '$ROOT_DIR/backend' && uv run pytest \
        tests/integration/test_conversation_routes.py::test_create_conversation_rate_limit_returns_429_before_dispatch \
        tests/integration/test_admin_user_routes.py \
        tests/integration/test_audit_repository.py \
        tests/integration/test_admin_analytics_dashboard_insights.py::test_admin_analytics_summary_and_queries_anonymize_athlete_identity \
        -q"

run_step "deterministic release checks" \
    bash -c "cd '$ROOT_DIR/backend' && uv run --group evals python -m evals.cli release-checks"

if [[ "$RUN_KB" == "true" ]]; then
    run_step "KB-service contract and redaction tests" \
        bash -c "cd '$ROOT_DIR/kb-service' && uv run pytest \
            tests/test_app/test_api_contract_routes.py \
            tests/test_core/test_logging_config.py \
            tests/test_core/test_log_redaction.py \
            -q"
fi

if [[ "$RUN_FRONTEND" == "true" ]]; then
    run_step "frontend typecheck" \
        bash -c "cd '$ROOT_DIR/frontend' && npm run typecheck"

    run_step "frontend lint" \
        bash -c "cd '$ROOT_DIR/frontend' && npm run lint"

    run_step "frontend tests" \
        bash -c "cd '$ROOT_DIR/frontend' && npm test -- --run"
fi

if [[ "$RUN_LIVE_EVALS" == "true" ]]; then
    run_step "live Langfuse-backed evals" \
        bash -c "cd '$ROOT_DIR/backend' && uv run --group evals python -m evals.cli run-all --strict --max-concurrency 5"
fi

echo
echo "Release validation passed."
