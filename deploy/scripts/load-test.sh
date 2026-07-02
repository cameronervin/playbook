#!/usr/bin/env bash
# Run Playbook Locust load tests with sanitized artifacts.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOAD_TEST_DIR="$ROOT_DIR/load-tests"
ARTIFACT_ROOT="${PLAYBOOK_LOAD_ARTIFACT_ROOT:-$ROOT_DIR/.artifacts/load-tests}"

TARGET="${1:-}"
if [[ -n "$TARGET" && "$TARGET" != -* ]]; then
    shift
else
    TARGET="local"
fi

PROFILE="${PLAYBOOK_LOAD_PROFILE:-smoke}"
USERS=""
SPAWN_RATE=""
RUN_TIME=""
API_BASE_URL="${PLAYBOOK_API_BASE_URL:-}"
KB_BASE_URL="${PLAYBOOK_KB_BASE_URL:-${STAGING_KB_BASE_URL:-}}"
STREAM_MODE="${PLAYBOOK_LOAD_STREAM_MODE:-enqueue}"
ALLOW_PRODUCTION_TARGET=false
DRY_RUN=false

usage() {
    cat <<'USAGE'
Usage: ./deploy/scripts/load-test.sh [local|staging|prod] [options]

Options:
  --profile smoke|baseline|live-agent|rate-limit
  --users N
  --spawn-rate N
  --run-time DURATION       Locust duration, e.g. 30s, 2m, 10m.
  --api-base-url URL        Backend API base URL. Defaults by target.
  --kb-base-url URL         Optional direct KB-service base URL.
  --stream-mode enqueue|wait
  --allow-production-target Require explicit approval for production-like targets.
  --dry-run                 Print the sanitized command without running Locust.
  -h, --help                Show this help.

Environment:
  PLAYBOOK_ATHLETE_BEARER_TOKENS       Comma-separated or JSON array.
  PLAYBOOK_ADMIN_BEARER_TOKENS         Comma-separated or JSON array.
  PLAYBOOK_SUPER_ADMIN_BEARER_TOKENS   Comma-separated or JSON array.
  PLAYBOOK_KB_API_SECRET               Required only for direct KB-service search.
  PLAYBOOK_LOAD_ORGANIZATION_ID        Required only for direct KB-service search.
  PLAYBOOK_LOAD_FAIL_RATIO_MAX         Defaults to 0.01.
  PLAYBOOK_LOAD_P95_MS                 Defaults to 1500.
  PLAYBOOK_LOAD_STREAM_P95_MS          Defaults to 60000.
USAGE
}

_is_production_like() {
    local target="$1"
    local url="$2"
    local lowered
    lowered="$(printf '%s %s' "$target" "$url" | tr '[:upper:]' '[:lower:]')"
    if [[ "$lowered" == *"prod"* || "$lowered" == *"production"* ]]; then
        return 0
    fi
    if [[ "$lowered" == *"localhost"* || "$lowered" == *"127.0.0.1"* || "$lowered" == *"staging"* || "$lowered" == *"stage"* || "$lowered" == *"dev"* || "$lowered" == *"sandbox"* ]]; then
        return 1
    fi
    if [[ "$url" == https://* ]]; then
        return 0
    fi
    return 1
}

require_tokens_for_staging() {
    if [[ "$TARGET" == "local" ]]; then
        return
    fi
    case "$PROFILE" in
        smoke|baseline|live-agent)
            if [[ -z "${PLAYBOOK_ATHLETE_BEARER_TOKENS:-}" || -z "${PLAYBOOK_ADMIN_BEARER_TOKENS:-}" ]]; then
                echo "PLAYBOOK_ATHLETE_BEARER_TOKENS and PLAYBOOK_ADMIN_BEARER_TOKENS are required for $TARGET $PROFILE load tests." >&2
                exit 2
            fi
            ;;
        rate-limit)
            if [[ -z "${PLAYBOOK_ATHLETE_BEARER_TOKENS:-}" ]]; then
                echo "PLAYBOOK_ATHLETE_BEARER_TOKENS is required for $TARGET rate-limit load tests." >&2
                exit 2
            fi
            ;;
    esac
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --profile)
            PROFILE="$2"
            shift
            ;;
        --users)
            USERS="$2"
            shift
            ;;
        --spawn-rate)
            SPAWN_RATE="$2"
            shift
            ;;
        --run-time)
            RUN_TIME="$2"
            shift
            ;;
        --api-base-url)
            API_BASE_URL="$2"
            shift
            ;;
        --kb-base-url)
            KB_BASE_URL="$2"
            shift
            ;;
        --stream-mode)
            STREAM_MODE="$2"
            shift
            ;;
        --allow-production-target)
            ALLOW_PRODUCTION_TARGET=true
            ;;
        --dry-run)
            DRY_RUN=true
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

case "$PROFILE" in
    smoke)
        DEFAULT_USERS=5
        DEFAULT_SPAWN_RATE=1
        DEFAULT_RUN_TIME="2m"
        USER_CLASSES=(PublicReadinessUser AthleteReadOnlyUser AdminReadOnlyUser)
        ;;
    baseline)
        DEFAULT_USERS=25
        DEFAULT_SPAWN_RATE=5
        DEFAULT_RUN_TIME="10m"
        USER_CLASSES=(PublicReadinessUser AthleteReadOnlyUser AdminReadOnlyUser)
        ;;
    live-agent)
        DEFAULT_USERS=5
        DEFAULT_SPAWN_RATE=1
        DEFAULT_RUN_TIME="10m"
        USER_CLASSES=(AthleteChatEnqueueUser AdminChatUser)
        if [[ -n "$KB_BASE_URL" && -n "${PLAYBOOK_KB_API_SECRET:-}" && -n "${PLAYBOOK_LOAD_ORGANIZATION_ID:-}" ]]; then
            USER_CLASSES+=(KBSearchUser)
        fi
        ;;
    rate-limit)
        DEFAULT_USERS=5
        DEFAULT_SPAWN_RATE=1
        DEFAULT_RUN_TIME="2m"
        USER_CLASSES=(RateLimitProbeUser)
        ;;
    *)
        echo "Unsupported load-test profile: $PROFILE" >&2
        usage >&2
        exit 1
        ;;
esac

USERS="${USERS:-$DEFAULT_USERS}"
SPAWN_RATE="${SPAWN_RATE:-$DEFAULT_SPAWN_RATE}"
RUN_TIME="${RUN_TIME:-$DEFAULT_RUN_TIME}"

if [[ -z "$API_BASE_URL" ]]; then
    case "$TARGET" in
        local)
            API_BASE_URL="http://localhost:8000"
            ;;
        staging)
            API_BASE_URL="${STAGING_API_BASE_URL:-}"
            ;;
        prod|production)
            API_BASE_URL="${PRODUCTION_API_BASE_URL:-}"
            ;;
    esac
fi

if [[ -z "$API_BASE_URL" ]]; then
    echo "API base URL is required. Pass --api-base-url or set STAGING_API_BASE_URL." >&2
    exit 2
fi

if [[ "$ALLOW_PRODUCTION_TARGET" != "true" ]] && _is_production_like "$TARGET" "$API_BASE_URL"; then
    echo "Refusing to load test a production-like target without --allow-production-target." >&2
    exit 2
fi

require_tokens_for_staging

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
ARTIFACT_DIR="$ARTIFACT_ROOT/${TIMESTAMP}-${TARGET}-${PROFILE}"
mkdir -p "$ARTIFACT_DIR"

export PLAYBOOK_API_BASE_URL="$API_BASE_URL"
export PLAYBOOK_KB_BASE_URL="$KB_BASE_URL"
export PLAYBOOK_LOAD_TARGET="$TARGET"
export PLAYBOOK_LOAD_PROFILE="$PROFILE"
export PLAYBOOK_LOAD_STREAM_MODE="$STREAM_MODE"
export PLAYBOOK_LOAD_ALLOW_PRODUCTION_TARGET="$ALLOW_PRODUCTION_TARGET"
export PLAYBOOK_LOAD_ARTIFACT_DIR="$ARTIFACT_DIR"

LOCUST_CMD=(
    uv run locust
    -f locustfile.py
    --headless
    --host "$API_BASE_URL"
    --users "$USERS"
    --spawn-rate "$SPAWN_RATE"
    --run-time "$RUN_TIME"
    --html "$ARTIFACT_DIR/report.html"
    --csv "$ARTIFACT_DIR/stats"
    --loglevel INFO
    "--playbook-profile=$PROFILE"
    "--playbook-target=$TARGET"
    "--playbook-stream-mode=$STREAM_MODE"
)

if [[ -n "$KB_BASE_URL" ]]; then
    LOCUST_CMD+=("--playbook-kb-host=$KB_BASE_URL")
fi
if [[ "$ALLOW_PRODUCTION_TARGET" == "true" ]]; then
    LOCUST_CMD+=(--playbook-allow-production-target)
fi
LOCUST_CMD+=("${USER_CLASSES[@]}")

echo "Playbook Locust load test"
echo "  target=$TARGET"
echo "  profile=$PROFILE"
echo "  api_base_url=$API_BASE_URL"
echo "  kb_base_url=$([[ -n "$KB_BASE_URL" ]] && echo set || echo unset)"
echo "  users=$USERS spawn_rate=$SPAWN_RATE run_time=$RUN_TIME stream_mode=$STREAM_MODE"
echo "  artifacts=$ARTIFACT_DIR"

if [[ "$DRY_RUN" == "true" ]]; then
    printf 'Dry run command:'
    printf ' %q' "${LOCUST_CMD[@]}"
    printf '\n'
    exit 0
fi

cd "$LOAD_TEST_DIR"
"${LOCUST_CMD[@]}"
