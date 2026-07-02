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
CI_MODE=false
RUN_SCANNERS=false
RUN_LIVE_EVALS=false
RUN_STAGING_SMOKE=false
RUN_STAGING_LOAD=false

usage() {
    cat <<'USAGE'
Usage: ./deploy/scripts/release-validate.sh [options]

Options:
  --ci              Run the fuller CI/release gate set.
  --include-scanners
                    Run OSS scanner and SBOM scripts after tests/evals.
  --live-evals       Also run Langfuse-backed evals with strict thresholds.
  --staging-smoke    Check STAGING_FRONTEND_URL and STAGING_API_BASE_URL.
  --staging-load     Run the staging Locust smoke load gate against STAGING_API_BASE_URL.
  --skip-frontend    Skip frontend lint, typecheck, and tests.
  --skip-kb          Skip KB-service contract/redaction tests.
  -h, --help         Show this help.

Environment:
  STAGING_FRONTEND_URL        Required with --staging-smoke.
  STAGING_API_BASE_URL        Required with --staging-smoke; /api/v1/ready is checked.
  STAGING_KB_BASE_URL         Optional KB-service URL for --staging-load live profiles.
  STAGING_LITELLM_HEALTH_URL  Optional LiteLLM readiness URL for smoke checks.
  STAGING_LOAD_PROFILE        Optional Locust profile; defaults to smoke.
  RELEASE_VALIDATE_BUILD_IMAGES
                              Set true to include image builds in scanner/SBOM scripts.
USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --ci)
            CI_MODE=true
            ;;
        --include-scanners)
            RUN_SCANNERS=true
            ;;
        --live-evals)
            RUN_LIVE_EVALS=true
            ;;
        --staging-smoke)
            RUN_STAGING_SMOKE=true
            ;;
        --staging-load)
            RUN_STAGING_LOAD=true
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

check_deploy_shell_syntax() {
    local script

    for script in "$ROOT_DIR"/deploy/scripts/*.sh; do
        bash -n "$script"
    done
}

run_step "deploy shell syntax checks" check_deploy_shell_syntax

run_backend_local_gate() {
    run_step "backend unit, eval, logging, auth, readiness, and rate-limit tests" \
        bash -c "cd '$ROOT_DIR/backend' && uv run pytest \
            tests/unit/test_rate_limit_service.py \
            tests/unit/evals \
            tests/unit/test_logging_config.py \
            tests/unit/test_log_redaction.py \
            tests/unit/test_langfuse_init.py \
            tests/unit/test_sentry_init.py \
            tests/unit/test_agent_trace.py \
            tests/unit/test_auth_dependencies.py \
            tests/unit/test_core_config.py \
            tests/unit/test_core_http.py \
            tests/unit/test_health_routes.py \
            -q"

    run_step "backend security/audit/rate-limit integration slice" \
        bash -c "cd '$ROOT_DIR/backend' && uv run pytest \
            tests/integration/test_auth_routes.py::test_oauth_callback_creates_session_without_exposing_provider_tokens \
            tests/integration/test_auth_routes.py::test_oauth_callback_redirects_browser_callers_after_setting_cookie \
            tests/integration/test_conversation_routes.py::test_create_conversation_rate_limit_returns_429_before_dispatch \
            tests/integration/test_admin_user_routes.py \
            tests/integration/test_release_authz_gates.py \
            tests/integration/test_audit_repository.py \
            tests/integration/test_admin_analytics_dashboard_insights.py::test_admin_analytics_summary_and_queries_anonymize_athlete_identity \
            -q"
}

run_backend_ci_gate() {
    run_step "backend full pytest suite" \
        bash -c "cd '$ROOT_DIR/backend' && uv run pytest -v"

    run_step "backend ruff" \
        bash -c "cd '$ROOT_DIR/backend' && uv run ruff check app tests"
}

if [[ "$CI_MODE" == "true" ]]; then
    run_backend_ci_gate
else
    run_backend_local_gate
fi

run_step "eval dataset validation" \
    bash -c "cd '$ROOT_DIR/backend' && uv run --group evals python -m evals.cli validate-datasets"

run_step "deterministic release checks" \
    bash -c "cd '$ROOT_DIR/backend' && uv run --group evals python -m evals.cli release-checks"

if [[ "$RUN_KB" == "true" ]]; then
    if [[ "$CI_MODE" == "true" ]]; then
        run_step "KB-service full pytest suite" \
            bash -c "cd '$ROOT_DIR/kb-service' && uv run pytest -v"

        run_step "KB-service ruff" \
            bash -c "cd '$ROOT_DIR/kb-service' && uv run ruff check app tests"
    else
        run_step "KB-service contract, config, readiness, and redaction tests" \
            bash -c "cd '$ROOT_DIR/kb-service' && uv run pytest \
                tests/test_config.py \
                tests/test_app/test_api_contract_routes.py \
                tests/test_core/test_logging_config.py \
                tests/test_core/test_log_redaction.py \
                tests/test_core/test_sentry_init.py \
                -q"
    fi
fi

if [[ "$RUN_FRONTEND" == "true" ]]; then
    run_step "frontend typecheck" \
        bash -c "cd '$ROOT_DIR/frontend' && npm run typecheck"

    run_step "frontend lint" \
        bash -c "cd '$ROOT_DIR/frontend' && npm run lint"

    run_step "frontend tests" \
        bash -c "cd '$ROOT_DIR/frontend' && npm test -- --run"

    if [[ "$CI_MODE" == "true" ]]; then
        run_step "frontend production build" \
            bash -c "cd '$ROOT_DIR/frontend' && npm run build"
    fi
fi

if [[ "$RUN_LIVE_EVALS" == "true" ]]; then
    run_step "live Langfuse-backed evals" \
        bash -c "cd '$ROOT_DIR/backend' && uv run --group evals python -m evals.cli run-all --strict --max-concurrency 5"
fi

if [[ "$RUN_SCANNERS" == "true" ]]; then
    SCANNER_IMAGE_ARG="--skip-images"
    if [[ "${RELEASE_VALIDATE_BUILD_IMAGES:-false}" == "true" ]]; then
        SCANNER_IMAGE_ARG="--build-images"
    fi

    run_step "OSS security scanner gate" \
        "$ROOT_DIR/deploy/scripts/security-scan.sh" "$SCANNER_IMAGE_ARG"

    run_step "CycloneDX SBOM generation" \
        "$ROOT_DIR/deploy/scripts/generate-sbom.sh" "$SCANNER_IMAGE_ARG"
fi

if [[ "$RUN_STAGING_SMOKE" == "true" ]]; then
    if [[ -z "${STAGING_FRONTEND_URL:-}" || -z "${STAGING_API_BASE_URL:-}" ]]; then
        echo "STAGING_FRONTEND_URL and STAGING_API_BASE_URL are required with --staging-smoke." >&2
        exit 2
    fi

    run_step "staging frontend smoke" \
        curl -fsS "${STAGING_FRONTEND_URL%/}/"

    run_step "staging backend readiness smoke" \
        curl -fsS "${STAGING_API_BASE_URL%/}/api/v1/ready"

    if [[ -n "${STAGING_LITELLM_HEALTH_URL:-}" ]]; then
        run_step "staging LiteLLM readiness smoke" \
            curl -fsS "$STAGING_LITELLM_HEALTH_URL"
    fi
fi

if [[ "$RUN_STAGING_LOAD" == "true" ]]; then
    if [[ -z "${STAGING_API_BASE_URL:-}" ]]; then
        echo "STAGING_API_BASE_URL is required with --staging-load." >&2
        exit 2
    fi

    LOAD_TEST_ARGS=(
        staging
        --profile "${STAGING_LOAD_PROFILE:-smoke}"
        --api-base-url "$STAGING_API_BASE_URL"
    )
    if [[ -n "${STAGING_KB_BASE_URL:-}" ]]; then
        LOAD_TEST_ARGS+=(--kb-base-url "$STAGING_KB_BASE_URL")
    fi
    if [[ -n "${PLAYBOOK_LOAD_STREAM_MODE:-}" ]]; then
        LOAD_TEST_ARGS+=(--stream-mode "$PLAYBOOK_LOAD_STREAM_MODE")
    fi

    run_step "staging Locust load gate" \
        "$ROOT_DIR/deploy/scripts/load-test.sh" "${LOAD_TEST_ARGS[@]}"
fi

echo
echo "Release validation passed."
