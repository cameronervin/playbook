# Hybrid Search and Reranking Phased Build

## Purpose

This handoff breaks KB-service hybrid search and reranking into small,
independently testable build phases. The goal is to let coding agents improve
retrieval quality without moving product authorization or prompt assembly out of
their current owners.

Target outcome:

- KB-service owns candidate generation, dedupe, hybrid ranking, and reranking.
- Backend preserves KB-service result order, assembles context, and persists
  citations.
- LiteLLM remains the single model gateway for KB-service.
- A self-hosted Infinity reranker provides the default cross-encoder path through
  the LiteLLM alias `playbook-rerank`.

## Current State

KB-service search is currently semantic-only:

1. `SearchService.search()` embeds the query through `playbook-embed`.
2. `AsyncVectorRepository.search()` runs pgvector cosine search.
3. Results are returned in cosine-distance order with `score = 1 - distance`.

Backend then deduplicates retrieved chunks and applies a relevance-band/source
date ranking pass before context assembly. That split is acceptable for the
current simple vector search, but it becomes leaky once KB-service merges vector
and lexical candidates or spends reranker budget.

Existing LiteLLM aliases:

| Alias | Current purpose |
|-------|-----------------|
| `playbook-chat` | Backend chat and eval judge calls |
| `playbook-fast` | Lightweight summaries and fast agent paths |
| `playbook-embed` | KB-service embeddings |
| `playbook-ocr` | Optional scanned PDF OCR |

## Target Architecture

```text
Backend LocalKBProvider
  -> kb-api /api/kb/search
    -> query embedding via LiteLLM model playbook-embed
    -> pgvector semantic candidates
    -> PostgreSQL full-text lexical candidates
    -> KB-service dedupe + reciprocal rank fusion
    -> LiteLLM /rerank model playbook-rerank
      -> self-hosted Infinity reranker
    -> final ranked chunks
  -> backend context assembly + citation persistence
```

Container shape:

```text
kb-api
  -> litellm:4000
       -> OpenAI for playbook-embed / playbook-fast / playbook-chat
       -> reranker:<port> for playbook-rerank
```

The reranker runs as its own Compose service on the internal Docker network.
Do not run the reranker model inside `kb-api` or `litellm`.

## Retrieval Ownership Rules

- KB-service owns final retrieval order after this build.
- KB-service dedupes before reranking so duplicate chunks do not consume reranker
  slots.
- KB-service must apply the same source-scope filters to semantic and lexical
  candidates.
- Backend may keep defensive dedupe during transition, but it must not reorder
  KB-service reranked results.
- Backend remains responsible for authenticated public routes, chat context
  assembly, final citation persistence, and safety/refusal policy.
- Frontend callers must never send arbitrary KB-service filters or choose
  `source_type`.

## Implementation Defaults

| Setting or behavior | Default |
|---------------------|---------|
| Reranker service | Infinity |
| Reranker model | `BAAI/bge-reranker-base` |
| LiteLLM rerank alias | `playbook-rerank` |
| KB-service rerank env | `LITELLM_RERANK_MODEL=playbook-rerank` |
| Search strategy default | Hybrid when enabled, semantic-only as fallback |
| Hybrid merge | Reciprocal rank fusion |
| Dedupe order | `chunk_id`, then exact text fallback |
| Reranker failure | Fail open to hybrid-ranked results |
| Logging posture | Structured metadata only; no raw large text or secrets |

Use Context7 before coding library-specific changes for LiteLLM rerank, pgvector,
PostgreSQL full-text search, and Infinity/reranker serving.

## Phase 0: Contracts and Docs Baseline

Scope:

- Reconcile KB-service search docs and schemas with implemented and target
  search behavior.
- Document `source_types`, private conversation scope, ranking metadata, and
  final `score` semantics before implementation changes.
- Add config placeholders for reranking:
  - `LITELLM_RERANK_MODEL`
  - `KB_RERANK_ENABLED`
  - `KB_RERANK_CANDIDATE_LIMIT`
  - `KB_RERANK_TIMEOUT_SECONDS`
  - `KB_RERANK_FAIL_OPEN`
- State that `score` is the final retrieval score exposed to callers, while raw
  semantic, lexical, hybrid, and rerank scores live in metadata.

Acceptance criteria:

- A coding agent can see current semantic-only behavior and the target hybrid
  rerank behavior without reading the whole repo.
- API docs and PRD retrieval docs agree on the intended request/response shape.
- No runtime behavior changes are required in this phase.

Do not do yet:

- Do not add migrations.
- Do not change search ordering.
- Do not add the reranker container.

## Phase 1: Self-Hosted Reranker Service

Scope:

- Add an Infinity reranker Compose service as a sibling of `litellm` and
  `kb-api`.
- Serve `BAAI/bge-reranker-base` by default.
- Add a LiteLLM model alias named `playbook-rerank` that points to the reranker
  service over the internal Docker network.
- Add local/prod env examples for `LITELLM_RERANK_MODEL=playbook-rerank` and any
  reranker service settings needed by Compose.
- Update LiteLLM virtual-key guidance so the KB-service key can call
  `playbook-embed`, `playbook-fast`, and `playbook-rerank`.

Acceptance criteria:

- Local Compose can start the reranker service with LiteLLM.
- A manual smoke call to LiteLLM `/rerank` ranks sample documents through
  `playbook-rerank`.
- If the reranker model is missing or unhealthy, LiteLLM returns a clear failure
  rather than silently routing to a non-rerank model.

Do not do yet:

- Do not call the reranker from KB-service.
- Do not require paid reranker provider keys.
- Do not bake model weights into a custom Dockerfile unless local image startup
  proves unreliable.

## Phase 2: KB-Service Reranker Provider

Scope:

- Add a KB-service reranker abstraction parallel to the existing embedder
  provider pattern.
- Implement a LiteLLM `/rerank` client with:
  - configurable model alias,
  - timeout,
  - top-N support,
  - structured request/response logging,
  - redaction of raw chunk text, source URIs, and secrets,
  - fail-open fallback to the input order when enabled.
- Cache/reuse HTTP clients using the same lifecycle care as existing LiteLLM
  clients.
- Normalize provider responses back to original chunk identities by candidate
  index.

Acceptance criteria:

- Fake provider tests prove request mapping: query, documents, model, and top-N.
- Response mapping preserves chunk IDs and applies rerank scores to the matching
  candidates.
- Timeout and 5xx failures return input order when `KB_RERANK_FAIL_OPEN=true`.
- Fail-closed behavior is testable when `KB_RERANK_FAIL_OPEN=false`.

Do not do yet:

- Do not change repository search SQL.
- Do not remove backend ranking yet.
- Do not log raw reranker inputs or returned document text.

## Phase 3: Hybrid Candidate Search

Scope:

- Add PostgreSQL full-text support for chunk text in
  `kb.langchain_pg_embedding`.
- Keep pgvector cosine search as semantic candidate retrieval.
- Add lexical candidate retrieval using PostgreSQL full-text search:
  - `websearch_to_tsquery`,
  - `ts_rank_cd`,
  - GIN index on the generated/searchable text vector.
- Apply identical collection, document status, organization, visibility, source
  type, conversation, and file filters to semantic and lexical candidate paths.
- Merge vector and lexical candidates with reciprocal rank fusion.
- Dedupe merged candidates by `chunk_id`, then exact text fallback.

Acceptance criteria:

- Vector-only, lexical-only, and hybrid matches can be returned.
- Shared filters are proven in repository tests for both candidate paths.
- Duplicate chunks from vector and lexical paths produce one rerank candidate.
- Existing semantic-only search can still be selected or used as fallback.

Do not do yet:

- Do not call the cross-encoder reranker from the repository.
- Do not let lexical search bypass private conversation-file filters.
- Do not change chunking settings in this phase.

## Phase 4: Search Orchestration and Response Metadata

Scope:

- Update `SearchService.search()` to orchestrate:
  1. resolve configuration,
  2. build trusted metadata filters,
  3. embed query,
  4. fetch semantic and lexical candidates,
  5. dedupe and reciprocal-rank candidates,
  6. rerank the bounded candidate list,
  7. return the final `limit` results.
- Include ranking metadata for observability and citation/debug support:
  - `semantic_score`,
  - `semantic_rank`,
  - `lexical_score`,
  - `lexical_rank`,
  - `hybrid_score`,
  - `rerank_score`,
  - `ranking_strategy`.
- Keep `score` as the final caller-facing retrieval score.
- Make semantic-only behavior configurable for local fallback and regression
  comparison.

Acceptance criteria:

- Final ordering comes from the reranker when reranking is enabled and healthy.
- Final ordering falls back to hybrid order when reranking fails open.
- `limit` is applied after reranking.
- Response metadata contains enough ranking detail for logs/evals without
  exposing raw model inputs.

Do not do yet:

- Do not let backend re-rank these final results.
- Do not expose provider-specific raw rerank payloads in the API.
- Do not make `priority` or `is_official` a ranking control.

## Phase 5: Backend Retrieval Cleanup

Scope:

- Treat KB-service result order as authoritative in `LocalKBProvider.search()`.
- Remove backend as primary ranking owner for KB-service results.
- Keep backend dedupe only as temporary defensive cleanup, preserving input order.
- Preserve context assembly, source-key generation, and citation persistence.
- Update backend tests that currently assert source-date ranking over KB-service
  order.

Acceptance criteria:

- Backend does not reorder KB-service reranked results.
- Citations still persist stable document, KB-service document, chunk, score, and
  source metadata.
- Unsupported/no-source policy behavior remains unchanged.

Do not do yet:

- Do not move answer safety policy into KB-service.
- Do not remove defensive backend dedupe until KB-service dedupe has production
  coverage.
- Do not cite summaries as evidence.

## Phase 6: Hardening, Evals, and Docs

Scope:

- Add golden retrieval/eval cases for:
  - acronym and keyword-heavy queries,
  - semantic paraphrase queries,
  - duplicate chunks,
  - reranker timeout/outage,
  - private conversation-file isolation,
  - deleted/failed/unready documents.
- Add local smoke coverage for:
  - LiteLLM `/rerank`,
  - KB-service hybrid search,
  - backend chat preserving ranked citations.
- Update docs after implementation:
  - KB-service retrieval and API contracts,
  - LiteLLM self-hosting guide,
  - deployment guide and env examples,
  - PRD KB-service retrieval/API docs.
- Track deferred shortcuts in `docs/development/tech-debt-tracker.md`.

Acceptance criteria:

- KB-service and backend tests pass for touched areas.
- Local smoke proves rerank path and fail-open path.
- Docs accurately describe which service owns retrieval order.
- Logs include request IDs, model aliases, candidate counts, and safe scores
  without raw large text, source URIs, secrets, or full model inputs.

Do not do yet:

- Do not add broad frontend UI changes unless a later product phase requires it.
- Do not introduce a paid reranker provider as the default.

## Test Matrix

| Area | Required scenarios |
|------|--------------------|
| Reranker service | Compose startup, LiteLLM `/rerank` smoke, missing model failure |
| KB reranker provider | Request mapping, response mapping, timeout, fail-open fallback |
| Hybrid repository | Vector-only hit, lexical-only hit, merged duplicate, shared filters |
| Ranking | RRF ordering, reranker override, stable tie handling |
| Dedupe | Same `chunk_id`, same text across docs, metadata preservation |
| Backend integration | Result order preserved, citations still persist |
| Security/logging | No raw large text, secrets, source URIs, or model inputs in logs |

## Open Follow-Ups

- Decide whether to upgrade from `BAAI/bge-reranker-base` to a larger reranker
  after golden retrieval evals establish a baseline.
- Decide whether production should run Infinity on CPU, GPU, or a dedicated model
  serving host based on latency and throughput measurements.
- Decide when to remove defensive backend dedupe after KB-service-owned dedupe is
  stable in deployed environments.
- Decide whether to expose ranking diagnostics to admin analytics or keep them
  log/eval-only.
