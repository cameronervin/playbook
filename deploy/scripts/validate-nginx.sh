#!/usr/bin/env bash
# Validate the production nginx config with a throwaway certificate.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TMP_PARENT="${TMPDIR:-/tmp}"
TMP_DIR="$(mktemp -d "$TMP_PARENT/playbook-nginx.XXXXXX")"

cleanup() {
    rm -rf "$TMP_DIR"
}
trap cleanup EXIT

if ! command -v openssl >/dev/null 2>&1; then
    echo "Error: openssl is required to create a temporary nginx test certificate." >&2
    exit 1
fi

CONTAINER_CMD=""
if command -v docker >/dev/null 2>&1; then
    CONTAINER_CMD="docker"
elif command -v podman >/dev/null 2>&1; then
    CONTAINER_CMD="podman"
else
    echo "Error: docker or podman is required for isolated nginx validation." >&2
    exit 1
fi

CERT_DIR="$TMP_DIR/letsencrypt/live/playbook"
mkdir -p "$CERT_DIR"

openssl req \
    -x509 \
    -nodes \
    -newkey rsa:2048 \
    -days 1 \
    -keyout "$CERT_DIR/privkey.pem" \
    -out "$CERT_DIR/fullchain.pem" \
    -subj "/CN=playbook.local" \
    >/dev/null 2>&1

"$CONTAINER_CMD" run --rm \
    --add-host frontend:127.0.0.1 \
    --add-host backend:127.0.0.1 \
    -v "$ROOT_DIR/deploy/docker/nginx.conf:/etc/nginx/nginx.conf:ro" \
    -v "$TMP_DIR/letsencrypt:/etc/letsencrypt:ro" \
    nginx:alpine nginx -t

echo "nginx config validation passed."
