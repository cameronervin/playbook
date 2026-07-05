#!/usr/bin/env bash
# Capture deploy readiness and migration evidence without printing env secrets.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_DIR="$ROOT_DIR/deploy/compose"
ENVS_DIR="$ROOT_DIR/deploy/envs"

ENVIRONMENT_NAME="prod"
OUTPUT_DIR="${EVIDENCE_DIR:-${TMPDIR:-/tmp}/playbook-deploy-evidence}"
SKIP_PUBLIC=false
FAILED=0

usage() {
    cat <<'USAGE'
Usage: ./deploy/scripts/readiness-evidence.sh [local|dev|prod] [options]

Options:
  --output-dir DIR  Directory for evidence logs.
  --skip-public     Skip public FRONTEND_URL/API_PUBLIC_URL probes.
  -h, --help        Show this help.

The evidence log records service status, internal health checks, nginx syntax,
and backend/KB Alembic migration state. It does not print env files or secrets.
USAGE
}

if [[ $# -gt 0 && "$1" =~ ^(local|dev|prod)$ ]]; then
    ENVIRONMENT_NAME="$1"
    shift
fi

while [[ $# -gt 0 ]]; do
    case "$1" in
        --output-dir)
            OUTPUT_DIR="${2:?Missing value for --output-dir}"
            shift 2
            ;;
        --skip-public)
            SKIP_PUBLIC=true
            shift
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
done

ENV_FILE="$ENVS_DIR/.env.$ENVIRONMENT_NAME"
if [[ "$ENVIRONMENT_NAME" == "prod" && ! -f "$ENV_FILE" ]]; then
    echo "Error: production env file not found at $ENV_FILE" >&2
    exit 1
fi

if command -v docker >/dev/null 2>&1; then
    CONTAINER_CMD=(docker compose)
elif command -v podman >/dev/null 2>&1; then
    CONTAINER_CMD=(podman compose)
else
    echo "Error: docker or podman compose is required." >&2
    exit 1
fi

mkdir -p "$OUTPUT_DIR"
chmod 700 "$OUTPUT_DIR"

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
EVIDENCE_FILE="$OUTPUT_DIR/readiness-${ENVIRONMENT_NAME}-${TIMESTAMP}.log"

exec > >(tee "$EVIDENCE_FILE") 2>&1

compose() {
    "${CONTAINER_CMD[@]}" -f "$COMPOSE_DIR/base.yml" -f "$COMPOSE_DIR/$ENVIRONMENT_NAME.yml" "$@"
}

env_value() {
    local key="$1"
    local value=""
    if [[ -f "$ENV_FILE" ]]; then
        value="$(awk -F= -v key="$key" '$1 == key {print $2; exit}' "$ENV_FILE" | sed 's/[[:space:]]*#.*$//' | xargs || true)"
    fi
    printf '%s' "$value"
}

service_defined() {
    compose config --services | grep -qx "$1"
}

service_running() {
    compose ps --services --filter status=running | grep -qx "$1"
}

run_required() {
    local label="$1"
    shift

    echo
    echo "==> $label"
    if "$@"; then
        echo "OK: $label"
    else
        echo "FAIL: $label"
        FAILED=1
    fi
}

run_optional_service_check() {
    local service="$1"
    local label="$2"
    shift 2

    if ! service_defined "$service"; then
        echo
        echo "==> $label"
        echo "SKIP: service '$service' is not defined for $ENVIRONMENT_NAME"
        return
    fi

    if ! service_running "$service"; then
        echo
        echo "==> $label"
        echo "FAIL: service '$service' is not running"
        FAILED=1
        return
    fi

    run_required "$label" "$@"
}

echo "Playbook deploy readiness evidence"
echo "Environment: $ENVIRONMENT_NAME"
echo "Timestamp: $TIMESTAMP"
echo "Evidence file: $EVIDENCE_FILE"

run_required "compose config resolves" compose config --quiet
run_required "compose service status" compose ps

run_optional_service_check "backend" "backend internal readiness" \
    compose exec -T backend curl -fsS http://127.0.0.1:8000/api/v1/ready

run_optional_service_check "kb-api" "KB-service internal health" \
    compose exec -T kb-api curl -fsS http://127.0.0.1:8001/health

run_optional_service_check "litellm" "LiteLLM internal readiness" \
    compose exec -T litellm python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:4000/health/readiness', timeout=5).read()"

run_optional_service_check "frontend" "frontend internal health" \
    compose exec -T frontend node -e "fetch('http://127.0.0.1:3000').then((response) => { if (!response.ok) process.exit(1); }).catch(() => process.exit(1))"

run_optional_service_check "backend" "backend Alembic migration state" \
    compose exec -T backend sh -c "alembic current && alembic heads"

run_optional_service_check "kb-api" "KB-service Alembic migration state" \
    compose exec -T kb-api sh -c "alembic current && alembic heads"

if service_defined "nginx"; then
    run_optional_service_check "nginx" "nginx config and local TLS health" \
        compose exec -T nginx sh -c "nginx -t && wget -qO- --no-check-certificate https://127.0.0.1/healthz >/dev/null"
fi

if [[ "$SKIP_PUBLIC" != "true" ]]; then
    API_PUBLIC_URL="${API_PUBLIC_URL:-$(env_value API_PUBLIC_URL)}"
    FRONTEND_URL="${FRONTEND_URL:-$(env_value FRONTEND_URL)}"

    if [[ -n "$API_PUBLIC_URL" && "$API_PUBLIC_URL" != *example.com* ]]; then
        run_required "public backend readiness" \
            curl -fsS --max-time 10 "${API_PUBLIC_URL%/}/api/v1/ready"
    else
        echo
        echo "==> public backend readiness"
        echo "SKIP: API_PUBLIC_URL is unset or still uses example.com"
    fi

    if [[ -n "$FRONTEND_URL" && "$FRONTEND_URL" != *example.com* ]]; then
        run_required "public frontend reachability" \
            curl -fsS --max-time 10 -o /dev/null "${FRONTEND_URL%/}/"
    else
        echo
        echo "==> public frontend reachability"
        echo "SKIP: FRONTEND_URL is unset or still uses example.com"
    fi
fi

echo
if [[ "$FAILED" -eq 0 ]]; then
    echo "Readiness evidence captured successfully: $EVIDENCE_FILE"
else
    echo "Readiness evidence captured with failures: $EVIDENCE_FILE"
fi

exit "$FAILED"
