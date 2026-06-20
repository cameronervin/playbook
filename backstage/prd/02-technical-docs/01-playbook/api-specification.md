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
| POST | `/conversations` | Start a new conversation from the first user message and start streamed generation | athlete |
| GET | `/conversations/{conversation_id}` | Get conversation with messages, citations, files | athlete-owner |
| POST | `/conversations/{conversation_id}/messages` | Submit follow-up user message and start streamed generation | athlete-owner |
| GET | `/conversations/{conversation_id}/messages/{message_id}/stream` | Stream assistant response chunks for the submitted task | athlete-owner |
| POST | `/conversations/{conversation_id}/files` | Create conversation-file direct-upload request | athlete-owner |
| POST | `/conversations/{conversation_id}/files/{file_id}/upload-complete` | Verify completed conversation-file upload | athlete-owner |

### Knowledge Base Admin

| Method | Endpoint | Purpose | Role |
|--------|----------|---------|------|
| GET | `/admin/kb/documents` | List KB documents and status | admin |
| POST | `/admin/kb/documents` | Create KB document direct-upload request | admin |
| POST | `/admin/kb/documents/{document_id}/upload-complete` | Verify completed KB document upload | admin |
| GET | `/admin/kb/documents/{document_id}` | Get document metadata/status | admin |
| PATCH | `/admin/kb/documents/{document_id}/metadata` | Update metadata tags and source date | admin |
| POST | `/admin/kb/documents/{document_id}/retry` | Retry failed/ready document processing | admin |
| DELETE | `/admin/kb/documents/{document_id}` | Delete or archive document | admin |

### Admin Analytics and Insights

| Method | Endpoint | Purpose | Role |
|--------|----------|---------|------|
| GET | `/admin/analytics/summary` | Query volume, topics, unanswered, risk summary | admin |
| GET | `/admin/analytics/queries` | Anonymized query list | admin |
| GET | `/admin/dashboard-insights/current` | Get latest completed dashboard insight output | admin |
| GET | `/admin/dashboard-insights/outputs` | List generated dashboard insight outputs | admin |
| GET | `/admin/dashboard-insights/outputs/{insight_id}` | Get one dashboard insight output | admin |
| GET | `/admin/dashboard-insights/runs` | List dashboard insight runs | admin |
| POST | `/admin/dashboard-insights/runs` | Start manual dashboard insight generation | admin |
| GET | `/admin/dashboard-insights/runs/{run_id}` | Get dashboard insight run status/output | admin |
| GET | `/admin/chat/sessions` | List current admin's chat sessions | admin |
| POST | `/admin/chat/sessions` | Create an admin chat side-panel session | admin |
| GET | `/admin/chat/sessions/{session_id}` | Get admin chat session with messages | admin-owner |
| POST | `/admin/chat/sessions/{session_id}/messages` | Ask an admin chat question and start streamed answer generation | admin-owner |
| GET | `/admin/chat/sessions/{session_id}/messages/{message_id}/stream` | Stream admin chat answer chunks for the submitted task | admin-owner |

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
Start a new conversation with the athlete's first message:

```json
POST /api/v1/conversations
{
  "content": "Can I accept this NIL deal?"
}
```

Response includes the created conversation, the persisted first user message, a
streaming assistant placeholder, and stream metadata. The conversation title is
an immediate provisional title from the first user message. The athlete chat
worker may replace it with an AI-generated title before publishing the terminal
stream `complete` event. `files` is a safe top-level list of conversation-scoped
uploads. It is usually empty when a conversation is first created, and later
includes file status summaries after direct-upload intents are created.

```json
{
  "conversation": {
    "id": "uuid",
    "organization_id": "uuid",
    "athlete_id": "uuid",
    "title": "Can I accept this NIL deal",
    "status": "active",
    "last_message_at": "2026-06-03T12:00:00Z",
    "created_at": "2026-06-03T12:00:00Z",
    "updated_at": "2026-06-03T12:00:00Z",
    "messages": [
      {
        "id": "uuid",
        "conversation_id": "uuid",
        "role": "user",
        "content": "Can I accept this NIL deal?",
        "status": "complete",
        "safety_outcome": null,
        "topic_labels": [],
        "risk_labels": [],
        "metadata": {"attached_file_ids": []},
        "citations": [],
        "created_at": "2026-06-03T12:00:00Z"
      },
      {
        "id": "uuid",
        "conversation_id": "uuid",
        "role": "assistant",
        "content": "",
        "status": "streaming",
        "safety_outcome": null,
        "topic_labels": [],
        "risk_labels": [],
        "metadata": {
          "task_id": "celery-task-uuid",
          "user_message_id": "uuid",
          "is_first_turn": true,
          "provisional_title": "Can I accept this NIL deal"
        },
        "citations": [],
        "created_at": "2026-06-03T12:00:00Z"
      }
    ],
    "files": []
  },
  "user_message_id": "uuid",
  "assistant_message_id": "uuid",
  "task_id": "celery-task-uuid",
  "stream_url": "/api/v1/conversations/uuid/messages/uuid/stream?task_id=celery-task-uuid",
  "status": "streaming"
}
```

Submit a follow-up message to an existing conversation:

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
  "task_id": "celery-task-uuid",
  "stream_url": "/api/v1/conversations/uuid/messages/uuid/stream?task_id=celery-task-uuid",
  "status": "streaming"
}
```

The first-send and follow-up message routes must enqueue a Celery task to
execute the athlete chat agent. The Celery worker publishes ordered lifecycle
and token events to Valkey Streams, with pub/sub notification for active HTTP
subscribers. The stream URL must be scoped to the athlete-owned conversation and
assistant message, and the backend must verify that the supplied `task_id`
belongs to that conversation/message before subscribing to the task's Valkey
stream/channel.

For first-turn streams, the terminal `complete` event may include
`conversation_title` when the separate conversation title graph successfully
replaces the provisional title:

```json
{
  "status": "complete",
  "task_id": "celery-task-uuid",
  "assistant_message_id": "uuid",
  "answer_type": "grounded_answer",
  "citation_count": 1,
  "conversation_title": "NIL Deal Disclosure"
}
```

### Upload Conversation File
```json
POST /api/v1/conversations/{conversation_id}/files
{
  "filename": "contract.pdf",
  "content_type": "application/pdf",
  "size_bytes": 123456,
  "message_id": null
}
```

Response:
```json
{
  "file": {
    "id": "uuid",
    "conversation_id": "uuid",
    "message_id": null,
    "filename": "contract.pdf",
    "content_type": "application/pdf",
    "size_bytes": 123456,
    "extraction_status": "upload_pending",
    "chunk_count": 0,
    "created_at": "2026-06-03T12:00:00Z",
    "updated_at": "2026-06-03T12:00:00Z"
  },
  "upload": {
    "upload_request_id": "uuid",
    "method": "POST",
    "url": "https://storage.example/upload",
    "fields": {
      "key": "conversation-files/originals/..."
    },
    "expires_at": "2026-06-03T12:15:00Z"
  }
}
```

After the browser uploads the binary to storage, it completes the request:

```json
POST /api/v1/conversations/{conversation_id}/files/{file_id}/upload-complete
{
  "upload_request_id": "uuid"
}
```

Completion verifies storage object metadata before returning the safe file
summary with `extraction_status: "uploaded"` and queues reliable private ingest
handoff. KB-service parsing, chunking, embedding, summaries, and private
retrieval happen outside the request path.

```json
{
  "id": "uuid",
  "conversation_id": "uuid",
  "message_id": null,
  "filename": "contract.pdf",
  "content_type": "application/pdf",
  "size_bytes": 123456,
  "extraction_status": "uploaded",
  "chunk_count": 0,
  "created_at": "2026-06-03T12:00:00Z",
  "updated_at": "2026-06-03T12:00:01Z"
}
```

After extraction completes, the file detail in conversation history includes
`extraction_status: "ready"` and `chunk_count`. Full extracted text references
and storage keys are internal and must not be returned to athletes unless a later
download/export feature explicitly requires them.

Conversation detail returns file attachments as a top-level `files` list. Each
file summary includes `id`, `conversation_id`, optional `message_id`, `filename`,
`content_type`, `size_bytes`, `extraction_status`, `chunk_count`, `created_at`,
and `updated_at`. It does not return storage keys, source URIs, presigned URLs,
or signed download URLs.

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
        "source_date": "2026-01-15"
      }
    }
  ],
  "created_at": "2026-06-03T12:00:00Z"
}
```

### Upload KB Document
```json
POST /api/v1/admin/kb/documents
{
  "filename": "nil-handbook.pdf",
  "content_type": "application/pdf",
  "size_bytes": 456789,
  "title": "NIL Handbook",
  "metadata_tags": {
    "topic": "nil"
  },
  "source_date": "2026-01-15"
}
```

Response:
```json
{
  "document": {
    "id": "uuid",
    "title": "NIL Handbook",
    "filename": "nil-handbook.pdf",
    "content_type": "application/pdf",
    "size_bytes": 456789,
    "processing_status": "upload_pending",
    "metadata_tags": {
      "topic": "nil"
    }
  },
  "upload": {
    "upload_request_id": "uuid",
    "method": "POST",
    "url": "https://storage.example/upload",
    "fields": {
      "key": "kb/originals/..."
    },
    "expires_at": "2026-06-03T12:15:00Z"
  }
}
```

After browser storage upload, complete the request:

```json
POST /api/v1/admin/kb/documents/{document_id}/upload-complete
{
  "upload_request_id": "uuid"
}
```

The backend verifies the object with storage `HEAD`, marks the document
`uploaded`, and queues KB-service ingest handoff. Browser callers never supply
`source_type`, organization IDs, storage keys, signed URLs, or KB-service IDs.

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

### Current Dashboard Insight
```json
GET /api/v1/admin/dashboard-insights/current?window=7d
{
  "id": "uuid",
  "run_id": "uuid",
  "summary": "NIL disclosure timing is the clearest support gap this week.",
  "headline_cards": [
    {
      "title": "NIL disclosure timing",
      "value": "18 related questions",
      "severity": "medium"
    }
  ],
  "topic_breakdown": [
    { "label": "NIL", "count": 48 }
  ],
  "recommended_attention_areas": [
    "Clarify NIL disclosure timing in athlete-facing guidance."
  ],
  "generated_at": "2026-06-03T12:00:00Z"
}
```

### Manual Dashboard Insight Run
```json
POST /api/v1/admin/dashboard-insights/runs
{
  "window_start": "2026-05-27T00:00:00Z",
  "window_end": "2026-06-03T00:00:00Z",
  "source_filters": {
    "topic_labels": ["nil", "compliance"]
  }
}
```

Response:
```json
{
  "run_id": "uuid",
  "status": "pending"
}
```

### Create Admin Chat Session
```json
POST /api/v1/admin/chat/sessions
{
  "title": "Weekly NIL questions",
  "context_window_start": "2026-05-27T00:00:00Z",
  "context_window_end": "2026-06-03T00:00:00Z"
}
```

Response:
```json
{
  "id": "uuid",
  "title": "Weekly NIL questions",
  "status": "active",
  "created_at": "2026-06-03T12:00:00Z"
}
```

### Admin Chat Question
```json
POST /api/v1/admin/chat/sessions/{session_id}/messages
{
  "question": "What are athletes most confused about this week?",
  "window": "7d"
}
```

Response:
```json
{
  "session_id": "uuid",
  "user_message_id": "uuid",
  "assistant_message_id": "uuid",
  "task_id": "celery-task-uuid",
  "stream_url": "/api/v1/admin/chat/sessions/uuid/messages/uuid/stream?task_id=celery-task-uuid",
  "status": "streaming"
}
```

The admin chat question route must enqueue a Celery task to execute the admin
chat agent. The worker publishes ordered lifecycle and token events to Valkey
Streams, with pub/sub notification for active HTTP subscribers. The stream URL
must be scoped to the admin-owned session and assistant message, and the backend
must verify that the supplied `task_id` belongs to that session/message before
subscribing to the task's Valkey stream/channel.

Final persisted assistant message shape:
```json
{
  "session_id": "uuid",
  "message_id": "uuid",
  "answer": "NIL disclosure timing is the most common confusion area...",
  "answer_type": "analytics_answer",
  "references": [
    { "type": "metric", "id": "top_topics.nil" },
    { "type": "dashboard_insight", "id": "uuid" }
  ]
}
```

The API stores both the admin question and assistant answer in
`admin_chat_messages`. The `session_id` must belong to the current admin and
organization. Dashboard insight runs are separate long-running jobs and remain
polled by `run_id`; only interactive agent responses use the streaming bridge.

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
