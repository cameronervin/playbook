# API Specification

Base URL: `/api/v1`

This document defines Playbook MVP API contracts for authentication, athlete chat, knowledgebase administration, admin analytics, and auditability.

<!-- V2 CHANGE: Replace scaffold Example endpoints with Playbook product APIs. -->

## Endpoint Summary

### Auth and Users

| Method | Endpoint | Purpose | Role |
|--------|----------|---------|------|
| GET | `/auth/providers` | List enabled OAuth providers | public |
| GET | `/auth/{provider}/login` | Start OAuth/OIDC login | public |
| GET | `/auth/{provider}/callback` | Complete OAuth/OIDC callback | public |
| POST | `/auth/logout` | End current session | authenticated |
| GET | `/users/me` | Return current user/profile | authenticated |
| PATCH | `/users/me/profile` | Complete/update athlete profile | athlete |
| GET | `/admin/users` | List users for role management | super_admin |
| PATCH | `/admin/users/{user_id}/role` | Update user role | super_admin |

### Athlete Chat

| Method | Endpoint | Purpose | Role |
|--------|----------|---------|------|
| GET | `/conversations` | List current athlete conversations | athlete |
| POST | `/conversations` | Create a new conversation | athlete |
| GET | `/conversations/{conversation_id}` | Get conversation with messages, citations, files | athlete-owner |
| POST | `/conversations/{conversation_id}/messages` | Submit user message and start streamed generation | athlete-owner |
| GET | `/conversations/{conversation_id}/messages/{message_id}/stream` | Stream assistant response chunks | athlete-owner |
| POST | `/conversations/{conversation_id}/files` | Upload conversation-scoped file | athlete-owner |

### Knowledge Base Admin

| Method | Endpoint | Purpose | Role |
|--------|----------|---------|------|
| GET | `/admin/kb/documents` | List KB documents and status | admin |
| POST | `/admin/kb/documents` | Upload KB document | admin |
| GET | `/admin/kb/documents/{document_id}` | Get document metadata/status | admin |
| PATCH | `/admin/kb/documents/{document_id}/metadata` | Update metadata tags, official flag, priority, source date | admin |
| POST | `/admin/kb/documents/{document_id}/retry` | Retry failed/ready document processing | admin |
| DELETE | `/admin/kb/documents/{document_id}` | Delete or archive document | admin |

### Admin Analytics and Insights

| Method | Endpoint | Purpose | Role |
|--------|----------|---------|------|
| GET | `/admin/analytics/summary` | Query volume, topics, unanswered, risk summary | admin |
| GET | `/admin/analytics/queries` | Anonymized query list | admin |
| GET | `/admin/insights/runs` | List insight runs | admin |
| POST | `/admin/insights/runs` | Start manual insight generation | admin |
| GET | `/admin/insights/runs/{run_id}` | Get run status/output | admin |
| POST | `/admin/insights/ask` | Talk-to-your-data side-panel question | admin |

### Governance

| Method | Endpoint | Purpose | Role |
|--------|----------|---------|------|
| GET | `/admin/audit-logs` | Query audit log records | super_admin |
| GET | `/health` | API health check | public |

## Request / Response Examples

### Current User
```json
GET /api/v1/users/me
{
  "id": "uuid",
  "email": "athlete@example.com",
  "name": "Jordan Athlete",
  "role": "athlete",
  "sport_team": "Basketball",
  "profile_complete": true
}
```

### Update Athlete Profile
```json
PATCH /api/v1/users/me/profile
{
  "name": "Jordan Athlete",
  "sport_team": "Basketball",
  "selected_role": "athlete"
}
```

Response:
```json
{
  "id": "uuid",
  "name": "Jordan Athlete",
  "role": "athlete",
  "sport_team": "Basketball",
  "next_route": "/chat"
}
```

### Submit Chat Message
```json
POST /api/v1/conversations/{conversation_id}/messages
{
  "content": "Can I accept this NIL deal?",
  "file_ids": ["uuid"]
}
```

Response:
```json
{
  "user_message_id": "uuid",
  "assistant_message_id": "uuid",
  "stream_url": "/api/v1/conversations/uuid/messages/uuid/stream",
  "status": "streaming"
}
```

### Assistant Message Shape
```json
{
  "id": "uuid",
  "role": "assistant",
  "content": "Short answer...",
  "status": "complete",
  "safety_outcome": null,
  "citations": [
    {
      "source_title": "NIL Policy Handbook",
      "rank": 1,
      "metadata": {
        "document_id": "uuid",
        "source_date": "2026-01-15",
        "is_official": true
      }
    }
  ],
  "created_at": "2026-06-03T12:00:00Z"
}
```

### Upload KB Document
```json
POST /api/v1/admin/kb/documents
Content-Type: multipart/form-data

file=@nil-handbook.pdf
metadata_tags={"topic":"nil","source_type":"policy"}
is_official=true
priority=10
source_date=2026-01-15
```

Response:
```json
{
  "id": "uuid",
  "title": "nil-handbook.pdf",
  "processing_status": "uploaded",
  "metadata_tags": {
    "topic": "nil",
    "source_type": "policy"
  }
}
```

### Analytics Summary
```json
GET /api/v1/admin/analytics/summary?window=7d
{
  "window_start": "2026-05-27T00:00:00Z",
  "window_end": "2026-06-03T00:00:00Z",
  "query_volume": 128,
  "top_topics": [
    { "label": "NIL", "count": 48 }
  ],
  "unanswered_count": 12,
  "risk_counts": {
    "nil": 22,
    "compliance": 14,
    "recruiting": 3
  }
}
```

### Manual Insight Run
```json
POST /api/v1/admin/insights/runs
{
  "window_start": "2026-05-27T00:00:00Z",
  "window_end": "2026-06-03T00:00:00Z"
}
```

Response:
```json
{
  "run_id": "uuid",
  "status": "pending"
}
```

### Talk-to-Your-Data Question
```json
POST /api/v1/admin/insights/ask
{
  "question": "What are athletes most confused about this week?",
  "window": "7d"
}
```

Response:
```json
{
  "answer": "NIL disclosure timing is the most common confusion area...",
  "references": [
    { "type": "metric", "id": "top_topics.nil" },
    { "type": "insight_run", "id": "uuid" }
  ]
}
```

## Error Response Contract

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "retryable": false
  }
}
```

## Authorization Rules

1. Athletes can only read and mutate their own conversations and files.
2. Admins can manage KB documents and view anonymized analytics.
3. Super admins can manage users, roles, and audit log queries.
4. Admin analytics must not return athlete names by default.
5. KB document operations must write audit records.
6. OAuth tokens must never be returned to the frontend after session creation.
