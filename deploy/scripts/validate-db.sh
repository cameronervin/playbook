#!/bin/bash
# PostgreSQL readiness check.
# Verifies the DB container is running and healthy, the database exists, and
# credentials work. Works with docker or podman.

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

CONTAINER_NAME="${DB_CONTAINER:-agentic-app-db-1}"
DB_USER="${DB_USER:-app}"
DB_NAME="${DB_NAME:-appdb}"

print_status() {
    if [ "$1" -eq 0 ]; then
        echo -e "${GREEN}OK${NC}  $2"
    else
        echo -e "${RED}FAIL${NC}  $2"
    fi
}

# Pick a container runtime
if command -v docker &> /dev/null; then
    CONTAINER_CMD="docker"
elif command -v podman &> /dev/null; then
    CONTAINER_CMD="podman"
else
    echo -e "${RED}Error: neither docker nor podman found${NC}"
    exit 1
fi

echo "=========================================="
echo "PostgreSQL Validation"
echo "Runtime:   $CONTAINER_CMD"
echo "Container: $CONTAINER_NAME"
echo "=========================================="

# 1. Container running
if $CONTAINER_CMD ps --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
    print_status 0 "Container is running"
else
    print_status 1 "Container '${CONTAINER_NAME}' is not running"
    echo -e "${YELLOW}Start it with: ./deploy/scripts/deploy.sh local${NC}"
    exit 1
fi

# 2. PostgreSQL accepting connections
if $CONTAINER_CMD exec "$CONTAINER_NAME" pg_isready -U "$DB_USER" &> /dev/null; then
    print_status 0 "PostgreSQL is accepting connections"
else
    print_status 1 "PostgreSQL is not ready"
    exit 1
fi

# 3. Database exists
DB_EXISTS=$($CONTAINER_CMD exec "$CONTAINER_NAME" psql -U "$DB_USER" -lqt \
    | cut -d \| -f 1 | grep -wc "$DB_NAME" || true)
if [ "$DB_EXISTS" -gt 0 ]; then
    print_status 0 "Database '$DB_NAME' exists"
else
    print_status 1 "Database '$DB_NAME' not found"
    exit 1
fi

# 4. Credentials work
if $CONTAINER_CMD exec "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" &> /dev/null; then
    print_status 0 "Credentials are valid"
else
    print_status 1 "Failed to authenticate"
    exit 1
fi

echo "=========================================="
echo -e "${GREEN}Validation complete.${NC}"
echo "=========================================="
