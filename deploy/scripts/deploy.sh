#!/bin/bash
set -e

# Deploy script for the agentic app scaffold.
# Usage: ./deploy.sh [local|dev|prod] [options]
#
# Options:
#   --build   Force rebuild images
#   --down    Stop services instead of starting
#   --logs    Follow logs after starting
#   --evidence Capture readiness/migration evidence after a detached start

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="$SCRIPT_DIR/../compose"
ENVS_DIR="$SCRIPT_DIR/../envs"
ENV=${1:-local}
shift || true

# Parse options
BUILD=""
DETACH=""
LOGS=""
DOWN=""
EVIDENCE=""

for arg in "$@"; do
    case $arg in
        --build) BUILD="--build" ;;
        --down)  DOWN="true" ;;
        --logs)  LOGS="true" ;;
        --evidence) EVIDENCE="true" ;;
        *) echo "Unknown option: $arg"; exit 1 ;;
    esac
done

# Validate environment
if [[ ! "$ENV" =~ ^(local|dev|prod)$ ]]; then
    echo "Error: invalid environment '$ENV'"
    echo "Usage: $0 [local|dev|prod] [--build] [--down] [--logs] [--evidence]"
    exit 1
fi

# Production requires a real (uncommitted) env file
if [[ "$ENV" == "prod" && ! -f "$ENVS_DIR/.env.prod" ]]; then
    echo "Error: production env file not found at $ENVS_DIR/.env.prod"
    echo "Create it from .env.prod.example with real values (do not commit it)."
    exit 1
fi

if [[ "$ENV" == "local" ]]; then
    for file in ".env.local" ".env.kb-service.local" ".env.litellm.local"; do
        if [[ ! -f "$ENVS_DIR/$file" ]]; then
            echo "Error: local env file not found at $ENVS_DIR/$file"
            echo "Create it from $file.example and fill in local placeholder values."
            exit 1
        fi
    done
fi

echo "=========================================="
echo "Environment: $ENV"
echo "Compose dir: $COMPOSE_DIR"
echo "=========================================="

export ENVIRONMENT=$ENV

COMPOSE_CMD="docker compose -f $COMPOSE_DIR/base.yml -f $COMPOSE_DIR/$ENV.yml"

# Stop services
if [[ "$DOWN" == "true" ]]; then
    echo "Stopping services..."
    $COMPOSE_CMD down
    echo "Services stopped."
    exit 0
fi

# Detach for non-local environments
if [[ "$ENV" != "local" ]]; then
    DETACH="-d"
fi

echo "Starting services..."
$COMPOSE_CMD up $BUILD $DETACH

if [[ "$EVIDENCE" == "true" ]]; then
    if [[ "$DETACH" == "-d" ]]; then
        "$SCRIPT_DIR/readiness-evidence.sh" "$ENV"
    else
        echo "Readiness evidence is available after detached starts only."
        echo "Run separately: $SCRIPT_DIR/readiness-evidence.sh $ENV"
    fi
fi

if [[ "$LOGS" == "true" && "$DETACH" == "-d" ]]; then
    $COMPOSE_CMD logs -f
fi

echo "=========================================="
echo "Done."
echo "  Logs:   $COMPOSE_CMD logs -f [service]"
echo "  Status: $COMPOSE_CMD ps"
echo "  Stop:   $0 $ENV --down"
echo "=========================================="
