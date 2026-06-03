# Integration Specification

This document defines how Playbook integrates with identity providers, the existing KB service, storage, async workers, and future athletic department systems.

## Current Scaffold Integrations

- Main backend to KB service over HTTP through `LocalKBProvider`.
- KB service to S3/LocalStack for staged document data.
- KB service to PostgreSQL/pgvector for vector storage.
- KB service to OpenAI embeddings directly or through LiteLLM gateway.
- Backend to LLM providers directly or through LiteLLM gateway.
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
2. File is stored securely and associated with conversation.
3. Extraction runs for that file.
4. Extracted text can be included in context for that conversation.
5. File is retained and visible in conversation history.
6. File is not added to shared KB in MVP.

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

## Insight Jobs

| Job | Trigger | Output |
|-----|---------|--------|
| Nightly query insights | Scheduled | `query_insight_runs`, `query_insights` |
| Manual query insights | Admin action | `query_insight_runs`, `query_insights` |

Insight jobs read conversation/query metadata and anonymized query text. They summarize topics, unanswered questions, and NIL/compliance/recruiting risk.

## Storage

| Data | Storage |
|------|---------|
| Admin KB originals | S3/LocalStack-compatible storage |
| Conversation files | S3/LocalStack-compatible storage |
| Parsed/chunked staging | KB service S3 staging |
| Vector embeddings | PostgreSQL + pgvector |
| Conversations/analytics/audit | Main backend PostgreSQL |

## Failure Handling

| Integration | Failure | Expected Behavior |
|-------------|---------|-------------------|
| OAuth provider | Callback/token exchange fails | No local session; retryable error |
| KB ingestion | Parse/chunk/embed fails | Document status `failed` with reason |
| KB search | Service unavailable | Chat returns graceful error or unsupported response |
| LLM provider | Generation fails | Stream shows recoverable failure and logs run ID |
| Insight job | Agent/job fails | Run status `failed`; dashboard shows failure |
| Storage | Upload fails | No ready record; admin/athlete sees clear error |
