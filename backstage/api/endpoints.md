# API Endpoints

Base URL: `/api/v1`

This document tracks the Playbook API surface. Keep it aligned with implemented
routes and the product API specification in
`backstage/prd/02-technical-docs/01-playbook/api-specification.md`.

## Conventions

| Rule | Detail |
|------|--------|
| Plural nouns | Use resource nouns such as `/conversations` and `/admin/kb/documents` |
| Versioned | All routes live under `/api/v1` |
| Thin routes | Routes validate input, call services, and return DTOs |
| Typed responses | Every route declares a Pydantic `response_model` once implemented |
| Auth | Protected routes require the app auth dependency or the selected OAuth integration |
| Errors | API errors use nested `{"error": {"code", "message", "retryable", "details"}}` payloads and include `details.request_id` when available |

Example error response:

```json
{
  "error": {
    "code": "FORBIDDEN",
    "message": "Admin role required",
    "retryable": false,
    "details": {
      "request_id": "request-id"
    }
  }
}
```

## Implemented

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Liveness/readiness check |
| GET | `/auth/providers` | List configured OAuth providers; includes local-only Developer SSO when dev auth is enabled |
| GET | `/auth/{provider}/login` | Return OAuth authorization URL and bind state cookie |
| GET | `/auth/{provider}/callback` | Complete OAuth callback and issue app session; browser callers receive a 303 redirect to `FRONTEND_URL + next_route` |
| POST | `/auth/session/refresh` | Refresh the current app session on authenticated user activity; returns `204` |
| POST | `/auth/logout` | Revoke the current app session when present and clear the session cookie |
| GET | `/users/me` | Return current authenticated user/profile |
| PATCH | `/users/me/profile` | Complete/update current athlete profile |
| GET | `/admin/users` | List organization users for super-admin role management |
| PATCH | `/admin/users/{user_id}/role` | Update a user's Playbook role |
| GET | `/conversations` | List current athlete conversations |
| POST | `/conversations` | Start a current-athlete conversation from the first message, enqueue the Celery agent task, and return `202` with `task_id` stream metadata plus conversation detail |
| GET | `/conversations/{conversation_id}` | Get conversation details with messages/citations/files |
| POST | `/conversations/{conversation_id}/files` | Create a conversation-scoped direct-upload request and return a presigned POST contract |
| POST | `/conversations/{conversation_id}/files/{file_id}/upload-complete` | Verify direct-uploaded object metadata and queue private ingest handoff |
| POST | `/conversations/{conversation_id}/messages` | Submit a follow-up user message, enqueue the Celery agent task, and return `202` with `task_id` stream metadata |
| GET | `/conversations/{conversation_id}/messages/{message_id}/stream` | Stream validated assistant response events as SSE from the Valkey stream for `task_id` |
| GET | `/admin/kb/documents` | List KB documents and status |
| POST | `/admin/kb/documents` | Create a KB document direct-upload request and return a presigned POST contract |
| POST | `/admin/kb/documents/{document_id}/upload-complete` | Verify direct-uploaded object metadata and queue KB-service ingest handoff |
| GET | `/admin/kb/documents/{document_id}` | Get document metadata/status |
| PATCH | `/admin/kb/documents/{document_id}/metadata` | Update metadata tags and source date |
| POST | `/admin/kb/documents/{document_id}/retry` | Retry document ingestion |
| DELETE | `/admin/kb/documents/{document_id}` | Delete backend document record, original file, and searchable KB vectors |
| POST | `/kb/webhook` | Receive signed KB-service status callbacks |
| GET | `/admin/audit-logs` | Query org-scoped audit log records |

## Direct Upload Endpoints

Admin KB documents and athlete conversation files use a two-step direct upload
contract. The intent routes accept JSON metadata only, create an
`upload_pending` backend resource, and return the safe resource plus an
`upload` object:

```json
{
  "upload_request_id": "uuid",
  "method": "POST",
  "url": "http://localhost:9000/playbook-bucket",
  "fields": {
    "key": "resource/originals/...",
    "Content-Type": "application/pdf"
  },
  "expires_at": "2026-06-17T12:15:00Z"
}
```

Browser clients submit a multipart form POST directly to `upload.url` with every
returned `field` and a final `file` part. After storage upload succeeds, clients
call the matching `upload-complete` route with `{ "upload_request_id": "uuid" }`.
The backend verifies object existence, size, and content type with storage
metadata before marking the resource `uploaded` and enqueueing durable
KB-service ingest handoff.

Normal conversation detail and admin document responses do not include storage
keys, source URIs, presigned URLs, or signed download URLs. See
[Direct Upload Flow](../architecture/direct-upload-flow.md) for the architecture
and failure paths.

## Local Development Only

These routes are absent unless the backend is running with
`DEV_AUTH_ENABLED=true`, `ENVIRONMENT=local` or `development`, and `DEBUG=true`.
They are for local browser validation only and must not be enabled in deployed
environments.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/auth/dev/login?persona={persona}` | Internal frontend contract for the login-screen Developer SSO role menu. Starts local fake SSO through the normal OAuth login/callback flow. `persona` defaults to `athlete`; valid values are `athlete`, `new_athlete`, `admin`, `super_admin`. For manual browser validation, prefer the login-screen Developer SSO menu. |

```bash
curl http://localhost:8000/api/v1/health
# {"status": "healthy"}
```

For a repeatable local Swagger and curl validation pass, see
[`phase1_endpoint_smoke.sh`](../../backend/scripts/phase1_endpoint_smoke.sh).

## Remaining Planned Surface

### Admin Analytics and Governance

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/admin/analytics/summary` | Query volume, topics, unanswered, risk summary |
| GET | `/admin/analytics/queries` | Anonymized query list |
| GET | `/admin/dashboard-insights/current` | Get latest completed insight output |
| GET | `/admin/dashboard-insights/outputs` | List generated insight outputs |
| GET | `/admin/dashboard-insights/runs` | List dashboard insight runs |
| POST | `/admin/dashboard-insights/runs` | Start manual insight generation; status is polled by `run_id` |
| GET | `/admin/chat/sessions` | List current admin chat sessions |
| POST | `/admin/chat/sessions` | Create an admin chat session |
| GET | `/admin/chat/sessions/{session_id}` | Get admin chat session details |
| POST | `/admin/chat/sessions/{session_id}/messages` | Ask an admin chat question, enqueue the Celery agent task, and return `task_id` stream metadata |
| GET | `/admin/chat/sessions/{session_id}/messages/{message_id}/stream` | Stream admin chat answer chunks from the Valkey stream/channel for the returned `task_id` |
