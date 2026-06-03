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
    error_message TEXT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);
```

Athlete files are conversation-scoped and not promoted into the shared KB in MVP.

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

### `query_insight_runs`
```sql
CREATE TABLE query_insight_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    requested_by UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    trigger_type VARCHAR(40) NOT NULL, -- nightly, manual
    status VARCHAR(40) NOT NULL DEFAULT 'pending',
    window_start TIMESTAMP WITH TIME ZONE NOT NULL,
    window_end TIMESTAMP WITH TIME ZONE NOT NULL,
    error_message TEXT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);
```

### `query_insights`
```sql
CREATE TABLE query_insights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES query_insight_runs(id) ON DELETE CASCADE,
    summary TEXT NOT NULL,
    topic_breakdown JSONB NOT NULL DEFAULT '[]',
    unanswered_questions JSONB NOT NULL DEFAULT '[]',
    risk_breakdown JSONB NOT NULL DEFAULT '[]',
    recommended_attention_areas JSONB NOT NULL DEFAULT '[]',
    generated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);
```

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

## Relationships

| Entity | Relationship |
|--------|--------------|
| `organizations` | Owns users, conversations, KB documents, insights, audit logs |
| `users` | Belongs to one organization; owns conversations and admin actions |
| `conversations` | Belongs to one athlete and contains messages/files |
| `conversation_messages` | Stores user/assistant messages, risk labels, and safety outcomes |
| `message_citations` | Links assistant messages to KB source records |
| `kb_documents` | Represents admin-uploaded searchable department documents |
| `query_insight_runs` | Tracks nightly/manual insight generation lifecycle |
| `query_insights` | Stores generated dashboard insight output |
| `audit_logs` | Immutable record of document and role admin actions |

## Future Model Hooks

- `organization_id` enables future multi-college support.
- `visibility_policy` enables future sport/team/audience document access.
- `role` can evolve into normalized role assignments if coach/compliance/NIL personas are added.
- `metadata_tags`, `is_official`, `priority`, and `source_date` support deterministic retrieval conflict handling.
