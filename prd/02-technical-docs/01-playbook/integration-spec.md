# Integration Specification

This document defines how Playbook integrates with identity providers, the existing KB service, storage, async workers, and future athletic department systems.

## Current Scaffold Integrations

- Main backend to KB service over HTTP through `LocalKBProvider`.
- KB service to S3-compatible storage for staged document data.
- KB service to PostgreSQL/pgvector for vector storage.
- KB service to embeddings through LiteLLM gateway by default.
- Backend to chat/completion models through LiteLLM gateway by default.
- Backend to PostgreSQL for LangGraph checkpoint persistence.
- Celery + Valkey for async ingestion and background jobs.

<!-- V2 CHANGE: Add Playbook OAuth/OIDC, chat-to-KB retrieval, admin document upload, nightly insights, and future system integration boundaries. -->

## Identity Providers

| Provider | Purpose | MVP Scope |
|----------|---------|-----------|
| Google OAuth/OIDC | User sign-in | Required |
| Microsoft OAuth/OIDC | User sign-in | Required |

Implementation notes:
1. Configure app registrations and redirect URLs per environment.
2. Store provider and provider subject on the local user record.
3. Use local roles for authorization; do not rely on provider groups for MVP.
4. Avoid paid auth vendors unless later requirements justify one.

## Knowledge Base Service

### Admin Document Flow

1. Admin uploads document through main backend.
2. Main backend stores original file in configured storage.
3. Main backend creates `kb_documents` record with `uploaded` status.
4. Main backend calls KB service ingestion endpoint or dispatches ingestion worker.
5. KB service parses, chunks, embeds, and writes vectors.
6. Main backend updates status to `processing`, `ready`, or `failed`.
7. Ready documents become eligible for chat retrieval.

### Search Flow

1. Athlete asks question.
2. Chat agent calls backend knowledgebase provider.
3. Provider calls KB service semantic search.
4. Results return document/chunk metadata.
5. Chat agent ranks results using score, source date, official flag, and priority.
6. Answer cites source titles at the bottom.

## Conversation File Uploads

Athlete-uploaded files are conversation-scoped.

1. Athlete uploads supported file to conversation.
2. Original file is stored securely in configured blob storage and associated with conversation.
3. Extraction runs for that file.
4. Full extracted text/page JSON is stored as a separate blob referenced by `conversation_files.extracted_text_ref`.
5. Extracted content is chunked into `conversation_file_chunks` for bounded chat context assembly.
6. File metadata and extraction status remain visible in conversation history.
7. File is not added to shared KB in MVP.

Conversation-file chunks are private to the owning conversation. The chat agent may
include selected chunks when the current message references uploaded files, but
shared KB search must exclude athlete-uploaded files.

Supported MVP file types:
- PDF
- DOCX
- PPTX
- XLSX

## External Athletic Systems

Systems mentioned for future interaction:
- Teamworks
- Opendorse
- NILGO

MVP boundary:
- Playbook answers "where/how" based on uploaded docs.
- Playbook may include links when docs contain them.
- Playbook does not perform direct API actions in those systems.

Future state:
- Add API integrations if provider APIs, auth, scopes, and costs support it.
- Actions must require explicit user confirmation and auditability.

## LLM Gateway

LiteLLM Proxy is the preferred production integration for all LLM and embedding
calls. Backend agents, KB-service embeddings, and eval jobs call LiteLLM model
aliases through an OpenAI-compatible API instead of storing provider API keys in
application services.

| Caller | Gateway Model Alias | Purpose |
|--------|---------------------|---------|
| Athlete chat agent | `playbook-chat` | Cited support answers |
| Dashboard insights agent | `playbook-chat` or `playbook-fast` | Nightly/manual insight generation |
| Admin chat side panel | `playbook-chat` | Analytics-grounded admin answers |
| KB-service ingestion | `playbook-embed` | Document chunk embeddings |
| Evaluation harness | `playbook-chat`, `playbook-embed` | Release and regression evals |

Gateway responsibilities:
1. Store provider credentials outside the backend, frontend, and KB-service app config.
2. Provide model aliases so app code does not depend on provider-specific model IDs.
3. Enforce virtual-key, rate-limit, budget, and spend-tracking policy per environment.
4. Support provider routing/fallbacks when configured.
5. Emit sanitized usage logs and alerts without raw prompts, file text, or secrets.

Direct provider mode is allowed only for local development, smoke tests, or an
explicit break-glass path. Production deployments should set application
services to `litellm` mode.

## Dashboard Insights and Admin Chat

| Job | Trigger | Output |
|-----|---------|--------|
| Nightly dashboard insights agent | Scheduled | `dashboard_insight_runs`, `dashboard_insights` |
| Manual dashboard insights agent | Admin action | `dashboard_insight_runs`, `dashboard_insights` |
| Admin chat side panel | Admin question | `admin_chat_sessions`, `admin_chat_messages` |

Dashboard insights agent runs read recent chats, conversation/message metadata,
and anonymized query text. They curate dashboard insight cards, summaries,
unanswered question groups, and NIL/compliance/recruiting risk attention areas.

The admin chat side panel reads authorized analytics, anonymized query text, and
stored dashboard insight records. It persists admin-only session/message history
separately from athlete conversations and must not expose athlete owner identity.

## Storage

| Data | Storage |
|------|---------|
| Admin KB originals | S3-compatible storage |
| Conversation file originals | S3-compatible storage |
| Conversation extracted text/page JSON | S3-compatible storage |
| Conversation file chunks | Main backend PostgreSQL |
| Parsed/chunked staging | KB service S3 staging |
| KB document vectors/chunk text | KB service PostgreSQL + pgvector |
| Conversations/analytics/audit/admin chat | Main backend PostgreSQL |

S3-compatible object storage is in MVP scope. Local development uses MinIO;
production should use private S3-compatible buckets with server-side
encryption, public access disabled, and short-lived signed URLs for
upload/download flows.

Recommended logical prefixes:

| Artifact | Prefix |
|----------|--------|
| Admin KB originals | `kb/originals/{organization_id}/{document_id}/{filename}` |
| KB-service staging | `kb/staging/{kb_service_document_id}/...` |
| Conversation file originals | `conversation-files/originals/{conversation_id}/{file_id}/{filename}` |
| Conversation extracted text/page JSON | `conversation-files/extracted/{conversation_id}/{file_id}/extracted.json` |

Storage rules:
1. Store only object keys in PostgreSQL, not signed URLs.
2. Keep buckets private and deny public ACLs.
3. Apply upload size limits and content-type allowlists before object creation.
4. Do not log object contents, signed URLs, provider keys, or extracted text.
5. Use lifecycle policy for failed/stale staging artifacts.
6. Keep athlete conversation uploads private to the owning conversation.

## LangGraph Checkpointer

Persistent LangGraph workflows use the `langgraph-checkpoint-postgres`
Postgres saver. Runtime startup calls the package `setup()` method to initialize
the checkpoint schema for the installed library version, then compiles graphs
with the saver.

Checkpoint data is infrastructure state, not user-facing domain data. It may
contain serialized graph state, message references, and intermediate run data,
so it must follow the same retention and logging restrictions as conversation
data.

Operational requirements:
1. Use `LANGGRAPH_CHECKPOINT_DB_URL` when checkpoint state should live in a
   separate database; otherwise use the main backend database.
2. Run package-managed setup/migrations before persistent agent traffic.
3. Prune old checkpoints according to `CHECKPOINT_RETENTION_DAYS`.
4. Do not expose checkpoint rows through product APIs.
5. Never store provider API keys or long-lived signed URLs in graph state.

## Failure Handling

| Integration | Failure | Expected Behavior |
|-------------|---------|-------------------|
| OAuth provider | Callback/token exchange fails | No local session; retryable error |
| KB ingestion | Parse/chunk/embed fails | Document status `failed` with reason |
| KB search | Service unavailable | Chat returns graceful error or unsupported response |
| LLM provider | Generation fails | Stream shows recoverable failure and logs run ID |
| Dashboard insights agent | Agent/job fails | Run status `failed`; dashboard shows failure |
| Storage | Upload fails | No ready record; admin/athlete sees clear error |
