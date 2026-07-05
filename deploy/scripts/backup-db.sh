#!/usr/bin/env bash
# Create an encrypted PostgreSQL custom-format dump from the Compose db service.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_DIR="$ROOT_DIR/deploy/compose"
ENVS_DIR="$ROOT_DIR/deploy/envs"

ENVIRONMENT_NAME="prod"
OUTPUT_DIR="${BACKUP_DIR:-${TMPDIR:-/tmp}/playbook-db-backups}"
BACKUP_NAME=""

usage() {
    cat <<'USAGE'
Usage: ./deploy/scripts/backup-db.sh [local|dev|prod] [options]

Options:
  --output-dir DIR  Directory for encrypted backups.
  --name NAME       Backup filename prefix. Defaults to playbook-<env>-db.
  -h, --help        Show this help.

Encryption:
  Set BACKUP_PASSPHRASE_FILE to a readable file or BACKUP_PASSPHRASE to a
  secret-manager-injected value. The passphrase is never printed.
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
        --name)
            BACKUP_NAME="${2:?Missing value for --name}"
            shift 2
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

if ! command -v openssl >/dev/null 2>&1; then
    echo "Error: openssl is required for encrypted database backups." >&2
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

if [[ -n "${BACKUP_PASSPHRASE_FILE:-}" ]]; then
    if [[ ! -r "$BACKUP_PASSPHRASE_FILE" ]]; then
        echo "Error: BACKUP_PASSPHRASE_FILE is not readable." >&2
        exit 1
    fi
    OPENSSL_PASS="file:$BACKUP_PASSPHRASE_FILE"
elif [[ -n "${BACKUP_PASSPHRASE:-}" ]]; then
    OPENSSL_PASS="env:BACKUP_PASSPHRASE"
else
    echo "Error: set BACKUP_PASSPHRASE_FILE or BACKUP_PASSPHRASE for encryption." >&2
    exit 1
fi

mkdir -p "$OUTPUT_DIR"
chmod 700 "$OUTPUT_DIR"

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_PREFIX="${BACKUP_NAME:-playbook-${ENVIRONMENT_NAME}-db}"
BACKUP_PATH="$OUTPUT_DIR/${BACKUP_PREFIX}-${TIMESTAMP}.dump.enc"

compose() {
    "${CONTAINER_CMD[@]}" -f "$COMPOSE_DIR/base.yml" -f "$COMPOSE_DIR/$ENVIRONMENT_NAME.yml" "$@"
}

echo "Creating encrypted database backup for environment: $ENVIRONMENT_NAME"
echo "Output: $BACKUP_PATH"

compose exec -T db sh -c '
    set -eu
    db_user="${POSTGRES_USER:-${DB_USER:-app}}"
    db_name="${POSTGRES_DB:-${DB_NAME:-playbook}}"
    pg_dump -U "$db_user" -d "$db_name" --format=custom --no-owner --no-acl
' | openssl enc -aes-256-cbc -pbkdf2 -salt -pass "$OPENSSL_PASS" -out "$BACKUP_PATH"

chmod 600 "$BACKUP_PATH"

if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$BACKUP_PATH" | tee "$BACKUP_PATH.sha256"
else
    sha256sum "$BACKUP_PATH" | tee "$BACKUP_PATH.sha256"
fi

echo "Encrypted database backup complete."
