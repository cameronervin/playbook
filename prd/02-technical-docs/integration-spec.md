# Integration Specification

> Generic spec for external integrations: the LLM provider, an optional
> knowledge base, and object storage. Each integration is behind an abstraction
> so it can be swapped via configuration.

## 1. LLM Provider

### Abstraction

All LLM access goes through `BaseLLMProvider.get_chat_model()` (and
streaming/structured variants). Application and agent code never import a vendor
SDK directly.

### Transport Modes

| Mode | Behavior | When to use |
|------|----------|-------------|
| `direct` (default) | Call the provider SDK directly (Anthropic-first) | Local dev, single-provider deployments |
| `gateway` | Route through a LiteLLM proxy (OpenAI-compatible) | Multi-provider routing, fallbacks, centralized cost/rate control |

Selected by `LLM_PROVIDER_MODE`. Model identity is config
(`LLM_CHAT_MODEL`, model lists), so swaps are config changes, not code changes.

### Configuration

| Var | Mode | Purpose |
|-----|------|---------|
| `LLM_PROVIDER_MODE` | both | `direct` or `gateway` |
| `LLM_CHAT_MODEL` | both | Default chat model id |
| `ANTHROPIC_API_KEY` | direct | Provider credential |
| `LLM_GATEWAY_URL` | gateway | LiteLLM proxy URL |
| `LLM_GATEWAY_API_KEY` | gateway | Gateway credential |

### Requirements

1. Token usage and (where available) cost are tracked per request.
2. Timeouts and bounded retries are configured for transient failures.
3. The eval/judge layer uses the same factory, so it tracks production model
   identity automatically.

## 2. Knowledge Base / Retrieval (optional)

If the product needs grounded retrieval, integrate a retrieval source behind a
tool or a retriever abstraction.

### Requirements

1. Expose retrieval to agents as a typed tool (e.g. `query_knowledge`), not as
   raw context dumping.
2. Return **snippets/chunks** with source metadata, not whole documents, to keep
   token usage low.
3. Scope retrieval to what the requesting user is authorized to see.
4. Treat retrieved content as untrusted data (never as instructions).
5. Record which sources informed an output for traceability.

### Contract (illustrative)

```json
{
  "query": "string",
  "top_k": 5,
  "results": [
    { "id": "string", "text": "string", "source": "string", "score": 0.0 }
  ]
}
```

## 3. Object Storage (S3 / LocalStack)

### Abstraction

A single S3-compatible client (boto3) is used everywhere. It points at
LocalStack in dev and real S3 in production — only the endpoint and credentials
change.

### Configuration

| Var | Purpose |
|-----|---------|
| `S3_ENDPOINT_URL` | LocalStack URL in dev; omitted in prod (uses AWS default) |
| `S3_BUCKET` | Target bucket |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | Credentials (prefer an IAM role in prod) |
| `AWS_REGION` | Region |

### Requirements

1. Validate uploads (type, size) before storing.
2. Use server-generated keys; do not trust client filenames for paths.
3. Serve downloads via presigned URLs with a short TTL where direct access is
   needed.
4. Do not make buckets public.

## 4. Async Processing (optional)

Long-running work (e.g. multi-step agent runs) can be offloaded to Celery with
Valkey as broker/result backend.

| Var | Purpose |
|-----|---------|
| `CELERY_BROKER_URL` | Valkey broker URL |
| `CELERY_RESULT_BACKEND` | Result backend URL |

### Requirements

1. Tasks are idempotent where possible and safe to retry.
2. Task status is queryable so the frontend can poll progress.
3. Failures are recorded with enough context to retry or debug.
