# KB Service Operations and Security

This document defines operational and security requirements for the Playbook KB
service MVP.

## Service Authentication

- All KB service endpoints except health checks require bearer service-to-service auth.
- Main backend to KB service credentials are environment secrets.
- Status webhooks from KB service to main backend are signed with HMAC-SHA256.
- Shared secrets must not be logged or returned in API responses.

## Data Protection

- Original file signed URLs are sensitive and should be short-lived.
- Logs must not include signed URLs, raw document contents, LiteLLM service keys,
  provider API keys, or embedding request bodies.
- Metadata should avoid unnecessary PII.
- Athlete conversation files must never be promoted into the shared KB corpus in MVP.

## LLM and Embedding Gateway

KB-service embeddings should use LiteLLM Proxy by default through a configured
embedding model alias such as `playbook-embed`. The KB service should hold only
the LiteLLM service key required to call the gateway; provider credentials remain
owned by the gateway.

KB-service reranking also routes through LiteLLM, using the
`LITELLM_RERANK_MODEL` alias (`playbook-rerank` by default). Search calls the
reranker only when `KB_SEARCH_STRATEGY=hybrid` and `KB_RERANK_ENABLED=true`;
semantic search remains the default fallback path.

Direct provider API keys are allowed only for local development, smoke tests, or
an explicit break-glass path. Production ingestion should not require OpenAI,
Anthropic, or other provider credentials in KB-service runtime configuration.

## Observability

Required structured log events:
- `kb_ingest_requested`
- `kb_parse_started`
- `kb_parse_completed`
- `kb_chunk_completed`
- `kb_embed_started`
- `kb_embed_batch_completed`
- `kb_load_vector_completed`
- `kb_ingest_failed`
- `kb_search_requested`
- `kb_search_completed`
- `kb_document_deleted`

Logs should include sanitized IDs such as `kb_service_document_id`,
`playbook_document_id`, `stage`, `status`, `duration_ms`, and counts. Logs should
not include raw extracted text or secret-bearing URLs.

## Metrics

Recommended MVP metrics:
- ingestion attempts by status,
- parse/chunk/embed/load duration,
- document failure count by reason,
- embedding provider latency/error rate,
- vector count per document,
- search latency,
- search result count and no-result rate.

## Failure Handling

| Failure | Handling |
|---------|----------|
| Source file unavailable | Mark failed with retryable reason |
| Unsupported file type | Mark failed with non-retryable reason |
| No text extracted | Mark failed with clear admin-facing reason |
| Parser crash | Retry within worker policy, then mark failed |
| Embedding provider outage | Retry with backoff, then mark failed/retryable |
| Vector count mismatch | Reissue missing chunks or mark failed with diagnostic count |
| Status webhook failure | Retry webhook delivery; retain local ingestion status |

## Configuration

Environment-configured values:
- service auth token,
- webhook signing secret,
- S3-compatible bucket and endpoint,
- Valkey broker URL,
- PostgreSQL/pgvector URL,
- embedding provider mode (`litellm` by default),
- LiteLLM base URL and service key,
- embedding model alias,
- summary model alias,
- reserved rerank model alias and rerank feature flags,
- chunk size and overlap,
- search default limit and score threshold,
- maximum upload size.

## Release Gates

Before enabling KB-backed answers:
- pgvector migration has run successfully,
- default configuration exists,
- service auth is enforced,
- status webhook signature validation works,
- ingestion succeeds for PDF/DOCX/PPTX/XLSX smoke files,
- search returns chunk text and required metadata,
- deleted/failed/unready documents are excluded from search.
