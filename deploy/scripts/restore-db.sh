#!/usr/bin/env bash
# Restore an encrypted PostgreSQL dump into an explicit Compose database target.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_DIR="$ROOT_DIR/deploy/compose"
ENVS_DIR="$ROOT_DIR/deploy/envs"

ENVIRONMENT_NAME="prod"
BACKUP_FILE=""
TARGET_DB=""
OVERWRITE=false
REPLACE_PRIMARY=false

usage() {
    cat <<'USAGE'
Usage: ./deploy/scripts/restore-db.sh [local|dev|prod] --backup-file FILE --target-db DB [options]

Options:
  --overwrite        Drop and recreate TARGET_DB if it already exists.
  --replace-primary  Allow TARGET_DB to match the environment's primary DB name.
  -h, --help         Show this help.

Encryption:
  Set BACKUP_PASSPHRASE_FILE to a readable file or BACKUP_PASSPHRASE to a
  secret-manager-injected value. The passphrase is never printed.

Recommended restore drill:
  ./deploy/scripts/restore-db.sh prod --backup-file /secure/path/backup.dump.enc \
    --target-db playbook_restore_drill
USAGE
}

if [[ $# -gt 0 && "$1" =~ ^(local|dev|prod)$ ]]; then
    ENVIRONMENT_NAME="$1"
    shift
fi

while [[ $# -gt 0 ]]; do
    case "$1" in
        --backup-file)
            BACKUP_FILE="${2:?Missing value for --backup-file}"
            shift 2
            ;;
        --target-db)
            TARGET_DB="${2:?Missing value for --target-db}"
            shift 2
            ;;
        --overwrite)
            OVERWRITE=true
            shift
            ;;
        --replace-primary)
            REPLACE_PRIMARY=true
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

if [[ -z "$BACKUP_FILE" || ! -r "$BACKUP_FILE" ]]; then
    echo "Error: --backup-file must point to a readable encrypted dump." >&2
    exit 1
fi

if [[ -z "$TARGET_DB" || ! "$TARGET_DB" =~ ^[A-Za-z0-9_]+$ ]]; then
    echo "Error: --target-db is required and may contain only letters, numbers, and underscores." >&2
    exit 1
fi

if ! command -v openssl >/dev/null 2>&1; then
    echo "Error: openssl is required to decrypt database backups." >&2
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
    echo "Error: set BACKUP_PASSPHRASE_FILE or BACKUP_PASSPHRASE for decryption." >&2
    exit 1
fi

env_value() {
    local key="$1"
    local value=""
    if [[ -f "$ENV_FILE" ]]; then
        value="$(awk -F= -v key="$key" '$1 == key {print $2; exit}' "$ENV_FILE" | sed 's/[[:space:]]*#.*$//' | xargs || true)"
    fi
    printf '%s' "$value"
}

PRIMARY_DB="${DB_NAME:-$(env_value DB_NAME)}"
if [[ -z "$PRIMARY_DB" || "$PRIMARY_DB" == "\${DB_NAME}" ]]; then
    PRIMARY_DB="playbook"
fi

if [[ "$TARGET_DB" == "$PRIMARY_DB" && "$REPLACE_PRIMARY" != "true" ]]; then
    echo "Error: refusing to restore over primary DB '$PRIMARY_DB' without --replace-primary." >&2
    exit 1
fi

compose() {
    "${CONTAINER_CMD[@]}" -f "$COMPOSE_DIR/base.yml" -f "$COMPOSE_DIR/$ENVIRONMENT_NAME.yml" "$@"
}

database_exists() {
    compose exec -T -e TARGET_DB="$TARGET_DB" db sh -c '
        set -eu
        db_user="${POSTGRES_USER:-${DB_USER:-app}}"
        psql -U "$db_user" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '\''$TARGET_DB'\''"
    ' | grep -q 1
}

if database_exists; then
    if [[ "$OVERWRITE" != "true" ]]; then
        echo "Error: target database '$TARGET_DB' already exists. Use --overwrite for a restore drill reset." >&2
        exit 1
    fi
    echo "Dropping existing target database: $TARGET_DB"
    compose exec -T -e TARGET_DB="$TARGET_DB" db sh -c '
        set -eu
        db_user="${POSTGRES_USER:-${DB_USER:-app}}"
        dropdb -U "$db_user" --if-exists "$TARGET_DB"
    '
fi

echo "Creating target database: $TARGET_DB"
compose exec -T -e TARGET_DB="$TARGET_DB" db sh -c '
    set -eu
    db_user="${POSTGRES_USER:-${DB_USER:-app}}"
    createdb -U "$db_user" "$TARGET_DB"
'

echo "Restoring encrypted backup into: $TARGET_DB"
openssl enc -d -aes-256-cbc -pbkdf2 -pass "$OPENSSL_PASS" -in "$BACKUP_FILE" | \
    compose exec -T -e TARGET_DB="$TARGET_DB" db sh -c '
        set -eu
        db_user="${POSTGRES_USER:-${DB_USER:-app}}"
        pg_restore -U "$db_user" -d "$TARGET_DB" --clean --if-exists --no-owner --no-acl --exit-on-error
    '

compose exec -T -e TARGET_DB="$TARGET_DB" db sh -c '
    set -eu
    db_user="${POSTGRES_USER:-${DB_USER:-app}}"
    psql -U "$db_user" -d "$TARGET_DB" -tAc "SELECT current_database(), now();"
'

echo "Database restore completed."
