# API Endpoints

Base URL: `/api/v1`

This document tracks the Playbook API surface. Keep it aligned with implemented
routes and the product API specification in
`prd/02-technical-docs/01-playbook/api-specification.md`.

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
| GET | `/auth/providers` | List configured Google/Microsoft OAuth providers |
| GET | `/auth/{provider}/login` | Return OAuth authorization URL and bind state cookie |
| GET | `/auth/{provider}/callback` | Complete OAuth callback and issue app session; browser callers receive a 303 redirect to `FRONTEND_URL + next_route` |
| POST | `/auth/logout` | Clear the current app session cookie |
| GET | `/users/me` | Return current authenticated user/profile |
| PATCH | `/users/me/profile` | Complete/update current athlete profile |
| GET | `/admin/users` | List organization users for super-admin role management |
| PATCH | `/admin/users/{user_id}/role` | Update a user's Playbook role |
| GET | `/conversations` | List current athlete conversations |
| POST | `/conversations` | Create a current-athlete conversation from the initial message |
| GET | `/conversations/{conversation_id}` | Get conversation details with messages/citations/files |
| POST | `/conversations/{conversation_id}/messages` | Submit a follow-up user message, enqueue the Celery agent task, and return `202` with `task_id` stream metadata |
| GET | `/admin/kb/documents` | List KB documents and status |
| POST | `/admin/kb/documents` | Upload KB document and request KB-service ingestion |
| GET | `/admin/kb/documents/{document_id}` | Get document metadata/status |
| PATCH | `/admin/kb/documents/{document_id}/metadata` | Update metadata tags, official flag, priority, and source date |
| POST | `/admin/kb/documents/{document_id}/retry` | Retry document ingestion |
| DELETE | `/admin/kb/documents/{document_id}` | Delete backend document record, original file, and searchable KB vectors |
| POST | `/kb/webhook` | Receive signed KB-service status callbacks |
| GET | `/admin/audit-logs` | Query org-scoped audit log records |

## Local Development Only

These routes are absent unless the backend is running with
`DEV_AUTH_ENABLED=true`, `ENVIRONMENT=local` or `development`, and `DEBUG=true`.
They are for local browser validation only and must not be enabled in deployed
environments.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/dev/session/{persona}` | Seed a deterministic local user, set the app session cookie, and redirect to the matching frontend route. Valid personas: `athlete`, `new_athlete`, `admin`, `super_admin` |

```bash
curl http://localhost:8000/api/v1/health
# {"status": "healthy"}
```

For a repeatable local Swagger and curl validation pass, see
[`phase1_backend_endpoint_validation.md`](../guides/phase1_backend_endpoint_validation.md).

## Remaining Planned Surface

### Athlete Chat

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/conversations/{conversation_id}/messages/{message_id}/stream` | Stream assistant response chunks from the Valkey stream/channel for the returned `task_id` |
| POST | `/conversations/{conversation_id}/files` | Upload a conversation-scoped file |

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
