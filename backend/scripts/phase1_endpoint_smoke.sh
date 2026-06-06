#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BASE="${BASE:-http://localhost:8000}"
SKIP_KB="${SKIP_KB:-0}"

if command -v uv >/dev/null 2>&1; then
  PYTHON_CMD=(uv run python)
elif [ -x "$BACKEND_DIR/.venv/bin/python" ]; then
  PYTHON_CMD=("$BACKEND_DIR/.venv/bin/python")
else
  PYTHON_CMD=(python)
fi

for required in curl jq openssl awk; do
  if ! command -v "$required" >/dev/null 2>&1; then
    printf 'Missing required command: %s\n' "$required" >&2
    exit 1
  fi
done

if [ -z "${ATHLETE_TOKEN:-}" ] || [ -z "${ADMIN_TOKEN:-}" ] || [ -z "${SUPER_TOKEN:-}" ]; then
  printf 'Seeding Phase 1 local validation users and tokens...\n'
  if ! SEED_EXPORTS="$(cd "$BACKEND_DIR" && "${PYTHON_CMD[@]}" scripts/phase1_dev_auth.py --format shell)"; then
    printf 'Failed to seed Phase 1 validation users.\n' >&2
    exit 1
  fi
  eval "$SEED_EXPORTS"
fi

TMP_DIR="$(mktemp -d)"
BODY_FILE="$TMP_DIR/body.json"
DOC_ID=""

cleanup() {
  if [ -n "$DOC_ID" ]; then
    curl -sS -X DELETE \
      -H "Authorization: Bearer $ADMIN_TOKEN" \
      "$BASE/api/v1/admin/kb/documents/$DOC_ID" >/dev/null || true
  fi
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

fail() {
  printf '\nFAIL: %s\n' "$1" >&2
  if [ -s "$BODY_FILE" ]; then
    printf 'Response body:\n' >&2
    cat "$BODY_FILE" >&2
    printf '\n' >&2
  fi
  exit 1
}

status_of() {
  curl -sS -o "$BODY_FILE" -w '%{http_code}' "$@"
}

expect_status() {
  local label="$1"
  local expected="$2"
  shift 2
  local status
  status="$(status_of "$@")"
  if [ "$status" != "$expected" ]; then
    fail "$label expected HTTP $expected, got $status"
  fi
  printf 'ok - %s\n' "$label"
}

expect_jq() {
  local label="$1"
  shift
  if ! jq -e "$@" "$BODY_FILE" >/dev/null; then
    fail "$label failed jq assertion"
  fi
}

printf 'Running Phase 1 endpoint smoke tests against %s\n' "$BASE"

expect_status "health" "200" "$BASE/api/v1/health"
expect_jq "health status" '.status == "healthy"'

expect_status "openapi" "200" "$BASE/openapi.json"
expect_jq "openapi includes Phase 1 paths" '.paths["/api/v1/users/me"] and .paths["/api/v1/admin/kb/documents"]'

expect_status "auth providers" "200" "$BASE/api/v1/auth/providers"
expect_jq "auth providers shape" '.providers | length == 2'

login_status="$(status_of "$BASE/api/v1/auth/google/login")"
case "$login_status" in
  200)
    expect_jq "configured google OAuth login" '.authorization_url | type == "string"'
    printf 'ok - google OAuth login configured\n'
    ;;
  400)
    expect_jq "disabled google OAuth login" '.error.code == "VALIDATION_ERROR"'
    printf 'ok - google OAuth login disabled with structured error\n'
    ;;
  *)
    fail "google OAuth login expected HTTP 200 or 400, got $login_status"
    ;;
esac

expect_status "users/me requires auth" "401" "$BASE/api/v1/users/me"

expect_status "athlete current user" "200" \
  -H "Authorization: Bearer $ATHLETE_TOKEN" \
  "$BASE/api/v1/users/me"
expect_jq "athlete current user role" '.role == "athlete"'

expect_status "athlete profile validation" "422" \
  -X PATCH "$BASE/api/v1/users/me/profile" \
  -H "Authorization: Bearer $ATHLETE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"","sport_team":""}'
expect_jq "athlete profile validation error" '.error.code == "VALIDATION_ERROR"'

expect_status "athlete profile update" "200" \
  -X PATCH "$BASE/api/v1/users/me/profile" \
  -H "Authorization: Bearer $ATHLETE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Jordan Athlete","sport_team":"Basketball"}'
expect_jq "athlete profile complete" '.profile_complete == true and .next_route == "/chat"'

expect_status "create athlete conversation" "201" \
  -X POST "$BASE/api/v1/conversations" \
  -H "Authorization: Bearer $ATHLETE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"NIL question"}'
CONV_ID="$(jq -r '.id // empty' "$BODY_FILE")"
if [ -z "$CONV_ID" ]; then
  fail "conversation create did not return id"
fi

expect_status "list athlete conversations" "200" \
  -H "Authorization: Bearer $ATHLETE_TOKEN" \
  "$BASE/api/v1/conversations"
expect_jq "conversation list includes created conversation" --arg id "$CONV_ID" 'map(.id) | index($id) != null'

expect_status "get athlete conversation detail" "200" \
  -H "Authorization: Bearer $ATHLETE_TOKEN" \
  "$BASE/api/v1/conversations/$CONV_ID"
expect_jq "conversation detail id" --arg id "$CONV_ID" '.id == $id'

expect_status "missing conversation returns 404" "404" \
  -H "Authorization: Bearer $ATHLETE_TOKEN" \
  "$BASE/api/v1/conversations/00000000-0000-0000-0000-000000000000"
expect_jq "missing conversation error" '.error.code == "NOT_FOUND"'

expect_status "athlete blocked from admin KB" "403" \
  -H "Authorization: Bearer $ATHLETE_TOKEN" \
  "$BASE/api/v1/admin/kb/documents"
expect_jq "athlete admin KB forbidden" '.error.code == "FORBIDDEN"'

expect_status "admin blocked from super-admin users" "403" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  "$BASE/api/v1/admin/users"
expect_jq "admin super-user forbidden" '.error.code == "FORBIDDEN"'

expect_status "super-admin list users" "200" \
  -H "Authorization: Bearer $SUPER_TOKEN" \
  "$BASE/api/v1/admin/users"
TARGET_ID="$(jq -r '.[] | select(.email=="role-target@example.com") | .id' "$BODY_FILE" | head -n 1)"
if [ -z "$TARGET_ID" ]; then
  fail "super-admin user list did not include role-target@example.com"
fi

expect_status "super-admin update role target" "200" \
  -X PATCH "$BASE/api/v1/admin/users/$TARGET_ID/role" \
  -H "Authorization: Bearer $SUPER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"role":"admin"}'
expect_jq "role target updated" '.role == "admin"'

if [ "$SKIP_KB" = "1" ]; then
  printf 'skip - KB document lifecycle skipped because SKIP_KB=1\n'
else
  expect_status "admin list KB documents" "200" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    "$BASE/api/v1/admin/kb/documents"

  printf '%s\n' 'Manual NIL policy smoke test' > "$TMP_DIR/playbook-nil-handbook.pdf"
  expect_status "KB upload rejects invalid metadata JSON" "400" \
    -X POST "$BASE/api/v1/admin/kb/documents" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -F 'metadata_tags=not-json' \
    -F "file=@$TMP_DIR/playbook-nil-handbook.pdf;type=application/pdf"
  expect_jq "KB invalid metadata error" '.error.code == "VALIDATION_ERROR"'

  printf '%s\n' 'plain notes' > "$TMP_DIR/plain-notes.txt"
  expect_status "KB upload rejects text/plain" "415" \
    -X POST "$BASE/api/v1/admin/kb/documents" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -F "file=@$TMP_DIR/plain-notes.txt;type=text/plain"
  expect_jq "KB unsupported file type error" '.error.code == "UNSUPPORTED_FILE_TYPE"'

  expect_status "KB upload PDF" "201" \
    -X POST "$BASE/api/v1/admin/kb/documents" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -F 'title=NIL Handbook' \
    -F 'metadata_tags={"topic":"nil","source_type":"policy"}' \
    -F 'source_date=2026-01-15' \
    -F 'is_official=true' \
    -F 'priority=10' \
    -F "file=@$TMP_DIR/playbook-nil-handbook.pdf;type=application/pdf"
  DOC_ID="$(jq -r '.id // empty' "$BODY_FILE")"
  if [ -z "$DOC_ID" ]; then
    fail "KB upload did not return id"
  fi
  expect_jq "KB upload metadata" '.metadata_tags.topic == "nil" and .is_official == true and .priority == 10'

  expect_status "KB get document" "200" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    "$BASE/api/v1/admin/kb/documents/$DOC_ID"

  expect_status "KB metadata update" "200" \
    -X PATCH "$BASE/api/v1/admin/kb/documents/$DOC_ID/metadata" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"metadata_tags":{"topic":"compliance"},"priority":3}'
  expect_jq "KB metadata updated" '.metadata_tags.topic == "compliance" and .priority == 3'

  expect_status "KB retry document" "200" \
    -X POST "$BASE/api/v1/admin/kb/documents/$DOC_ID/retry" \
    -H "Authorization: Bearer $ADMIN_TOKEN"
  expect_jq "KB retry status" '.processing_status == "uploaded"'

  if [ -z "${KB_WEBHOOK_SECRET:-}" ]; then
    KB_WEBHOOK_SECRET="$(cd "$BACKEND_DIR" && "${PYTHON_CMD[@]}" - <<'PY'
from app.core.config import settings
print(settings.KB_WEBHOOK_SECRET)
PY
)"
  fi
  if [ -z "$KB_WEBHOOK_SECRET" ]; then
    : > "$BODY_FILE"
    fail "KB_WEBHOOK_SECRET is empty; set it to test signed webhook success"
  fi

  expect_status "KB webhook missing signature" "403" \
    -X POST "$BASE/api/v1/kb/webhook" \
    -H "Content-Type: application/json" \
    -d "{\"document_id\":\"$DOC_ID\",\"stage\":\"pipeline\",\"status\":\"success\"}"
  expect_jq "KB webhook missing signature error" '.error.code == "FORBIDDEN"'

  WEBHOOK_BODY="$(jq -nc --arg id "$DOC_ID" --argjson ts "$(date +%s)" '{document_id:$id,stage:"pipeline",status:"success",timestamp:$ts,metadata:{task_id:"manual-smoke"}}')"
  SIG="$(printf '%s' "$WEBHOOK_BODY" | openssl dgst -sha256 -hmac "$KB_WEBHOOK_SECRET" -r | awk '{print $1}')"
  expect_status "KB webhook signed success" "200" \
    -X POST "$BASE/api/v1/kb/webhook" \
    -H "Content-Type: application/json" \
    -H "X-KB-Signature: sha256=$SIG" \
    --data "$WEBHOOK_BODY"
  expect_jq "KB webhook ready status" '.status == "ok" and .document_status == "ready"'

  expect_status "super-admin audit KB upload" "200" \
    -H "Authorization: Bearer $SUPER_TOKEN" \
    "$BASE/api/v1/admin/audit-logs?action=kb.document_uploaded"
  expect_jq "audit includes KB upload" --arg id "$DOC_ID" 'map(.target_id) | index($id) != null'

  expect_status "KB delete document" "204" \
    -X DELETE "$BASE/api/v1/admin/kb/documents/$DOC_ID" \
    -H "Authorization: Bearer $ADMIN_TOKEN"
  DOC_ID=""
fi

expect_status "super-admin audit role change" "200" \
  -H "Authorization: Bearer $SUPER_TOKEN" \
  "$BASE/api/v1/admin/audit-logs?action=user.role_changed"
expect_jq "audit includes role change" --arg id "$TARGET_ID" 'map(.target_id) | index($id) != null'

printf 'Phase 1 endpoint smoke tests completed successfully.\n'
