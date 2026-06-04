# Data Model

This document defines the Playbook MVP data model for an athlete-first agentic support prototype on the existing scaffold.

## Current Baseline

The repository currently includes scaffold/example tables and a KB service schema:

- Backend scaffold: `examples`.
- KB service: `configurations`, `documents`, `ingestion_logs`, `langchain_pg_collection`, `langchain_pg_embedding`.

<!-- V2 CHANGE: Replace scaffold Example domain with Playbook user, conversation, document, analytics, and audit models. -->

## Proposed Playbook Tables

### `organizations`
```sql
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(120) UNIQUE NOT NULL,
    theme_config JSONB NOT NULL DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);
```

MVP uses one organization. The table preserves future multi-college tenancy without putting any protected school affiliation into code identifiers.

### `users`
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    email VARCHAR(320) NOT NULL,
    name VARCHAR(255) NOT NULL,
    role VARCHAR(40) NOT NULL DEFAULT 'athlete',
    auth_provider VARCHAR(40) NOT NULL,
    provider_subject VARCHAR(255) NOT NULL,
    sport_team VARCHAR(255) NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    UNIQUE (organization_id, email),
    UNIQUE (auth_provider, provider_subject)
);
```

Allowed MVP roles:
- `athlete`
- `admin`
- `super_admin`

### `conversations`
```sql
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    athlete_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NULL,
    status VARCHAR(40) NOT NULL DEFAULT 'active',
    last_message_at TIMESTAMP WITH TIME ZONE NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);
```

### `conversation_messages`
```sql
CREATE TABLE conversation_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(40) NOT NULL, -- user, assistant, system
    content TEXT NOT NULL,
    status VARCHAR(40) NOT NULL DEFAULT 'complete', -- pending, streaming, complete, failed, declined
    safety_outcome VARCHAR(80) NULL,
    topic_labels JSONB NOT NULL DEFAULT '[]',
    risk_labels JSONB NOT NULL DEFAULT '[]',
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);
```

### `message_citations`
```sql
CREATE TABLE message_citations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL REFERENCES conversation_messages(id) ON DELETE CASCADE,
    document_id UUID NULL,
    chunk_id UUID NULL,
    source_title VARCHAR(500) NOT NULL,
    source_metadata JSONB NOT NULL DEFAULT '{}',
    rank INT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);
```

`document_id` and `chunk_id` may reference KB-service records through a local mirrored identifier or cross-service identifier.

### `conversation_files`
```sql
CREATE TABLE conversation_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    message_id UUID NULL REFERENCES conversation_messages(id) ON DELETE SET NULL,
    uploaded_by UUID NOT NULL REFERENCES users(id),
    filename VARCHAR(500) NOT NULL,
    content_type VARCHAR(120) NOT NULL,
    size_bytes BIGINT NOT NULL,
    storage_key VARCHAR(1000) NOT NULL,
    extraction_status VARCHAR(40) NOT NULL DEFAULT 'uploaded',
    extracted_text_ref VARCHAR(1000) NULL,
    extracted_text_sha256 VARCHAR(64) NULL,
    extracted_char_count INT NULL,
    extraction_metadata JSONB NOT NULL DEFAULT '{}',
    error_message TEXT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);
```

`storage_key` points to the original uploaded binary in configured blob storage.
`extracted_text_ref` points to the full extracted text/page JSON artifact in blob
storage. Full extracted text is not stored directly on this row to avoid
accidentally loading large file contents during conversation list/detail queries.

Extraction statuses:
- `uploaded`
- `extracting`
- `ready`
- `failed`

Athlete files are conversation-scoped and not promoted into the shared KB in MVP.
They may be used as private context for the owning conversation only.

### `conversation_file_chunks`
```sql
CREATE TABLE conversation_file_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id UUID NOT NULL REFERENCES conversation_files(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    text TEXT NOT NULL,
    token_count INT NULL,
    source_locator JSONB NOT NULL DEFAULT '{}',
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    UNIQUE (file_id, chunk_index)
);
```

`conversation_file_chunks` stores the bounded runtime representation of extracted
athlete-uploaded files. The chat agent can select ordered chunks from this table
without loading the entire extracted text artifact into the prompt. `source_locator`
captures user-facing position hints such as page number, slide number, sheet name,
row range, or paragraph range when the extractor can provide them.

### `kb_documents`
```sql
CREATE TABLE kb_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    uploaded_by UUID NOT NULL REFERENCES users(id),
    title VARCHAR(500) NOT NULL,
    filename VARCHAR(500) NOT NULL,
    content_type VARCHAR(120) NOT NULL,
    size_bytes BIGINT NOT NULL,
    storage_key VARCHAR(1000) NOT NULL,
    processing_status VARCHAR(40) NOT NULL DEFAULT 'uploaded',
    failure_reason TEXT NULL,
    visibility_policy JSONB NOT NULL DEFAULT '{"scope":"all_athletes"}',
    metadata_tags JSONB NOT NULL DEFAULT '{}',
    source_date DATE NULL,
    is_official BOOLEAN NOT NULL DEFAULT false,
    priority INT NOT NULL DEFAULT 0,
    kb_service_document_id UUID NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);
```

Processing statuses:
- `uploaded`
- `processing`
- `ready`
- `failed`

### `kb_document_events`
```sql
CREATE TABLE kb_document_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES kb_documents(id) ON DELETE CASCADE,
    event_type VARCHAR(80) NOT NULL,
    status VARCHAR(40) NULL,
    message TEXT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);
```

### `dashboard_insight_runs`
```sql
CREATE TABLE dashboard_insight_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    requested_by UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    trigger_type VARCHAR(40) NOT NULL, -- nightly, manual
    status VARCHAR(40) NOT NULL DEFAULT 'pending',
    window_start TIMESTAMP WITH TIME ZONE NOT NULL,
    window_end TIMESTAMP WITH TIME ZONE NOT NULL,
    source_filters JSONB NOT NULL DEFAULT '{}',
    error_message TEXT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);
```

### `dashboard_insights`
```sql
CREATE TABLE dashboard_insights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES dashboard_insight_runs(id) ON DELETE CASCADE,
    summary TEXT NOT NULL,
    headline_cards JSONB NOT NULL DEFAULT '[]',
    topic_breakdown JSONB NOT NULL DEFAULT '[]',
    unanswered_questions JSONB NOT NULL DEFAULT '[]',
    risk_breakdown JSONB NOT NULL DEFAULT '[]',
    recommended_attention_areas JSONB NOT NULL DEFAULT '[]',
    source_message_ids JSONB NOT NULL DEFAULT '[]',
    generated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);
```

`dashboard_insight_runs` tracks the lifecycle of the dashboard insights agent.
`dashboard_insights` stores the agent-curated dashboard output generated from
recent chats and anonymized analytics for a bounded time window. These records
power the admin dashboard insight cards and summaries; they are distinct from
interactive admin chat history.

### `admin_chat_sessions`
```sql
CREATE TABLE admin_chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    created_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NULL,
    status VARCHAR(40) NOT NULL DEFAULT 'active',
    context_window_start TIMESTAMP WITH TIME ZONE NULL,
    context_window_end TIMESTAMP WITH TIME ZONE NULL,
    last_message_at TIMESTAMP WITH TIME ZONE NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);
```

`admin_chat_sessions` stores admin-only chat sessions in the dashboard side
panel. These sessions are separate from athlete `conversations` because they
operate over anonymized analytics and dashboard insight data, not athlete support
messages.

### `admin_chat_messages`
```sql
CREATE TABLE admin_chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES admin_chat_sessions(id) ON DELETE CASCADE,
    role VARCHAR(40) NOT NULL, -- user, assistant, system
    content TEXT NOT NULL,
    status VARCHAR(40) NOT NULL DEFAULT 'complete',
    references JSONB NOT NULL DEFAULT '[]',
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);
```

`references` stores the metrics, anonymized query IDs, or dashboard insight
records used to answer the admin question. Admin chat message content must not
include athlete names by default. If an athlete includes identifying text inside
their own query, the analytics layer should still avoid exposing owner identity
in admin chat references.

### `audit_logs`
```sql
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    actor_user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(120) NOT NULL,
    target_type VARCHAR(120) NOT NULL,
    target_id UUID NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);
```

## Infrastructure-Owned Tables

These tables are required for Playbook infrastructure but are not product-domain
models. They should not be exposed through product APIs.

### LangGraph Postgres Checkpointer

Persistent LangGraph agent state is stored by
`langgraph-checkpoint-postgres`. The application should initialize this schema
through `AsyncPostgresSaver.setup()` during startup or migration setup for the
installed package version instead of maintaining hand-written ORM models for
checkpoint rows.

Expected scaffold-owned tables:

| Table | Purpose |
|-------|---------|
| `langgraph_checkpoints` | Stores serialized checkpoint state by thread/checkpoint namespace |
| `langgraph_checkpoint_writes` | Stores pending/intermediate channel writes associated with checkpoints |

Depending on the installed `langgraph-checkpoint-postgres` version, package
setup may also create migration, blob, or metadata tables. Treat all
`langgraph_checkpoint%` tables as package-owned unless the library version
documents a different naming scheme.

Checkpoint requirements:
1. Thread IDs must map to product-scoped identifiers such as conversation ID,
   dashboard insight run ID, or admin chat session ID.
2. Checkpoint payloads may contain serialized graph state and must follow the
   same retention and access restrictions as conversation data.
3. No provider API keys, refresh tokens, long-lived signed URLs, or raw secrets
   may be written into graph state.
4. Old checkpoint rows should be pruned according to `CHECKPOINT_RETENTION_DAYS`.
5. If `LANGGRAPH_CHECKPOINT_DB_URL` is configured, these tables live in that
   database; otherwise they live in the main backend PostgreSQL database.

## Relationships

| Entity | Relationship |
|--------|--------------|
| `organizations` | Owns users, conversations, KB documents, dashboard insights, admin chat sessions, audit logs |
| `users` | Belongs to one organization; owns conversations and admin actions |
| `conversations` | Belongs to one athlete and contains messages/files |
| `conversation_messages` | Stores user/assistant messages, risk labels, and safety outcomes |
| `message_citations` | Links assistant messages to KB source records |
| `conversation_files` | Stores original-file and extracted-text blob references for athlete uploads |
| `conversation_file_chunks` | Stores conversation-scoped extracted chunks used for chat context |
| `kb_documents` | Represents admin-uploaded searchable department documents |
| `dashboard_insight_runs` | Tracks nightly/manual dashboard insights agent lifecycle |
| `dashboard_insights` | Stores agent-curated dashboard insight output |
| `admin_chat_sessions` | Stores admin-only dashboard side-panel chat sessions |
| `admin_chat_messages` | Stores admin chat questions, answers, and analytics references |
| `audit_logs` | Immutable record of document and role admin actions |
| `langgraph_checkpoint%` | Package-owned persisted graph state for agent workflows |

## Future Model Hooks

- `organization_id` enables future multi-college support.
- `visibility_policy` enables future sport/team/audience document access.
- `role` can evolve into normalized role assignments if coach/compliance/NIL personas are added.
- `metadata_tags`, `is_official`, `priority`, and `source_date` support deterministic retrieval conflict handling.
- `conversation_file_chunks` can later gain private conversation-scoped embeddings,
  but those vectors must remain filtered by `conversation_id`/owner and separate
  from the shared KB corpus.
