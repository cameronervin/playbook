# Phase 1 Backend Endpoint Validation

Use this guide to validate the implemented Phase 1 backend API surface with
Swagger and curl against a local backend at `http://localhost:8000`.

The protected endpoint pass uses local throwaway JWTs instead of real OAuth.
This is useful when Google and Microsoft providers are not configured in local
development.

## Prerequisites

- Backend server is running on port `8000`.
- Backend database migrations have been applied.
- `curl`, `jq`, and `openssl` are available.
- For KB document upload tests, storage must be reachable and the backend should
  use either `KB_PROVIDER_MODE=mock` or a reachable local KB service.
- For signed webhook success, `KB_WEBHOOK_SECRET` must be set in the environment
  used by the running backend.

## Seed Dev Auth

From `backend/`, seed throwaway users and export app JWTs:

```bash
eval "$(.venv/bin/python scripts/phase1_dev_auth.py --format shell)"
```

If `uv` is available, this equivalent command also works:

```bash
eval "$(uv run python scripts/phase1_dev_auth.py --format shell)"
```

The command creates or reuses:

| Export | Role | Email |
|--------|------|-------|
| `ATHLETE_TOKEN` | `athlete` | `phase1-athlete@example.com` |
| `ADMIN_TOKEN` | `admin` | `phase1-admin@example.com` |
| `SUPER_TOKEN` | `super_admin` | `phase1-super@example.com` |
| `ROLE_TARGET_ID` | `athlete` | `role-target@example.com` |

The role target is reset to `athlete` each time the seed command runs so the
role-management smoke test is repeatable.

## Browser Cookie Pass

For local frontend/UI validation without configured Google or Microsoft OAuth,
enable the dev-only browser bootstrap route:

```env
DEV_AUTH_ENABLED=true
ENVIRONMENT=local
DEBUG=true
```

Then open one of these URLs in the browser:

```text
http://localhost:8000/api/v1/dev/session/athlete
http://localhost:8000/api/v1/dev/session/new_athlete
http://localhost:8000/api/v1/dev/session/admin
http://localhost:8000/api/v1/dev/session/super_admin
```

The route seeds the same throwaway users, sets the normal HttpOnly
`access_token` cookie, and redirects to the configured frontend URL. The route
is not registered unless `DEV_AUTH_ENABLED=true` and the backend is running in
local/development debug mode.

## Swagger Pass

1. Open `http://localhost:8000/docs`.
2. Click **Authorize**.
3. Paste the raw JWT value only. Swagger sends it as
   `Authorization: Bearer <token>`.
4. Re-authorize with the athlete, admin, and super-admin tokens as needed.

Validate:

- Public routes: `GET /api/v1/health`, `GET /api/v1/auth/providers`, and
  `GET /api/v1/auth/google/login`.
- Athlete routes: `GET /api/v1/users/me`,
  `PATCH /api/v1/users/me/profile`, and conversation list/create-from-initial-message/detail.
- Admin routes: KB document list/upload/get/metadata/retry/delete.
- Super-admin routes: user list, role update, and audit log query.
- Webhook error path: call `POST /api/v1/kb/webhook` without
  `X-KB-Signature` and expect `403 FORBIDDEN`.

## Curl Smoke Runner

Run the scripted Phase 1 pass:

```bash
cd backend
bash scripts/phase1_endpoint_smoke.sh
```

The script seeds tokens automatically when `ATHLETE_TOKEN`, `ADMIN_TOKEN`, and
`SUPER_TOKEN` are not already exported.

Useful options:

```bash
BASE=http://localhost:8000 bash scripts/phase1_endpoint_smoke.sh
SKIP_KB=1 bash scripts/phase1_endpoint_smoke.sh
KB_WEBHOOK_SECRET=local-secret bash scripts/phase1_endpoint_smoke.sh
```

`SKIP_KB=1` keeps auth, profile, RBAC, conversations, user management, and audit
checks enabled while skipping storage-backed KB document lifecycle checks.

## Expected Coverage

- Provider listing works, disabled OAuth login returns structured
  `VALIDATION_ERROR`, and protected routes return `401` without a token.
- Athlete profile completion returns `next_route: /chat`; blank fields return
  `422 VALIDATION_ERROR`.
- Athlete users cannot access admin KB routes, and admin users cannot access
  super-admin routes.
- Athletes can create conversations from an initial message, list them, and get
  their own conversation details.
- Super admins can update the role target and query the resulting audit event.
- KB document upload, metadata update, retry, signed webhook, audit, and delete
  work when storage and KB dependencies are configured.
