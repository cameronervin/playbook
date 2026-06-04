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

## Implemented

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Liveness/readiness check |

```bash
curl http://localhost:8000/api/v1/health
# {"status": "ok"}
```

## Planned Playbook Surface

### Auth and Users

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/auth/providers` | List enabled OAuth providers |
| GET | `/auth/{provider}/login` | Start OAuth/OIDC login |
| GET | `/auth/{provider}/callback` | Complete OAuth/OIDC callback |
| POST | `/auth/logout` | End current session |
| GET | `/users/me` | Return current user/profile |
| PATCH | `/users/me/profile` | Complete/update athlete profile |
| GET | `/admin/users` | List users for role management |
| PATCH | `/admin/users/{user_id}/role` | Update user role |

### Athlete Chat

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/conversations` | List current athlete conversations |
| POST | `/conversations` | Create a new conversation |
| GET | `/conversations/{conversation_id}` | Get conversation details |
| POST | `/conversations/{conversation_id}/messages` | Submit a user message |
| GET | `/conversations/{conversation_id}/messages/{message_id}/stream` | Stream assistant response chunks |
| POST | `/conversations/{conversation_id}/files` | Upload a conversation-scoped file |

### Knowledge Base Admin

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/admin/kb/documents` | List KB documents and status |
| POST | `/admin/kb/documents` | Upload KB document |
| GET | `/admin/kb/documents/{document_id}` | Get document metadata/status |
| PATCH | `/admin/kb/documents/{document_id}/metadata` | Update document metadata |
| POST | `/admin/kb/documents/{document_id}/retry` | Retry document processing |
| DELETE | `/admin/kb/documents/{document_id}` | Delete or archive document |

### Admin Analytics and Governance

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/admin/analytics/summary` | Query volume, topics, unanswered, risk summary |
| GET | `/admin/analytics/queries` | Anonymized query list |
| GET | `/admin/dashboard-insights/current` | Get latest completed insight output |
| GET | `/admin/dashboard-insights/outputs` | List generated insight outputs |
| GET | `/admin/dashboard-insights/runs` | List dashboard insight runs |
| POST | `/admin/dashboard-insights/runs` | Start manual insight generation |
| GET | `/admin/chat/sessions` | List current admin chat sessions |
| POST | `/admin/chat/sessions` | Create an admin chat session |
| GET | `/admin/chat/sessions/{session_id}` | Get admin chat session details |
| POST | `/admin/chat/sessions/{session_id}/messages` | Ask an admin chat question |
| GET | `/admin/audit-logs` | Query audit log records |
