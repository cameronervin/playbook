# KB Service Retrieval

This document defines the current retrieval behavior for shared Playbook KB
documents and private conversation-file context, plus the reserved contract
shape for reranking.

## Search Scope

Search includes only admin-uploaded KB documents that are:
- successfully ingested,
- owned by the requested `organization_id`,
- not deleted or archived,
- visible to the requesting audience,
- in the configured Playbook collection.

Athlete conversation files are never eligible for shared KB search. The
conversation-file RAG path uses KB-service private retrieval with a separate
trusted scope from the backend.

## Query Flow

1. Main backend receives an athlete chat message.
2. Chat orchestration decides whether KB retrieval is required.
3. Main backend calls KB service search with query, organization ID, source type
   scope, limit, threshold, and visibility context.
4. KB service embeds the query through the configured embedding provider.
5. KB service runs pgvector cosine similarity search against ready vectors.
   When `KB_SEARCH_STRATEGY=hybrid`, it also runs PostgreSQL full-text lexical
   search over chunk text and merges semantic plus lexical candidates with
   reciprocal-rank fusion.
6. KB service returns chunk text, final caller-facing `score`, document IDs, and
   metadata.
7. Main backend currently keeps defensive dedupe and near-similar source-date
   ordering during the retrieval-order transition.
8. Assistant answer cites returned sources through `message_citations`.

Current hybrid candidate flow plus later rerank flow:

```text
query embedding
  -> semantic pgvector candidates
  -> PostgreSQL full-text lexical candidates
  -> KB-service dedupe + reciprocal-rank fusion
  -> LiteLLM /rerank using LITELLM_RERANK_MODEL
  -> final ranked chunks
```

Phase 2 added the internal LiteLLM `/rerank` provider, Phase 3 added lexical
candidate retrieval and reciprocal-rank fusion behind
`KB_SEARCH_STRATEGY=hybrid`, and Phase 4 wires the optional reranker into
hybrid search when `KB_RERANK_ENABLED=true`.

## Required Filtering

MVP visibility policy defaults to:

```json
{ "scope": "all_athletes" }
```

Search must still carry a visibility context so future team/sport audience
filtering can be added without changing the API shape.

Search must also carry a top-level trusted `organization_id`. KB service search
filters vector metadata with this organization scope before returning chunks;
vectors without organization metadata are not eligible for retrieval.

Source-type filters are mandatory:

| Source type | Required filters |
|-------------|------------------|
| `admin_upload` | `organization_id`, `source_type="admin_upload"`, visibility policy |
| `conversation_file` | `organization_id`, `source_type="conversation_file"`, `conversation_id`, optional `file_ids` |

If `source_types` is omitted, KB-service searches only `admin_upload` chunks.
If `conversation_file` search omits `conversation_id`, KB-service rejects the
request before vector search. Combined retrieval may return both source types
only when the backend supplies the trusted private conversation scope.

## Ranking Signals

Default runtime ranking is semantic-only:
- `score` is `1 - pgvector cosine_distance` after the request threshold is
  applied,
- rows are ordered by ascending cosine distance in KB-service,
- backend may still dedupe and prefer newer `source_date` within near-similar
  relevance bands until the later backend cleanup phase.

When `KB_SEARCH_STRATEGY=hybrid`, KB-service retrieves bounded semantic and
lexical candidates, dedupes them by `chunk_id` then exact text, and ranks them
with reciprocal-rank fusion. If `KB_RERANK_ENABLED=false`, hybrid `score` is
the final `hybrid_score` exposed to callers for that mode. If
`KB_RERANK_ENABLED=true`, KB-service sends up to `KB_RERANK_CANDIDATE_LIMIT`
hybrid-ranked candidates to LiteLLM `/rerank`, applies the request `limit`
after reranking, and uses the reranker `relevance_score` as the final `score`
when the reranker returns one. Retryable fail-open reranker failures preserve
hybrid ordering and hybrid scores.

`score_threshold` remains a semantic candidate-generation threshold. Hybrid RRF
scores and rerank relevance scores are strategy-specific final scores and are
not post-filtered by the semantic cosine threshold.

Raw ranking diagnostics remain in `metadata`:
- `semantic_score`,
- `semantic_rank`,
- `lexical_score`,
- `lexical_rank`,
- `hybrid_score`,
- `rerank_score`,
- `ranking_strategy`.

Admin-uploaded shared KB documents are official by definition for MVP, and
priority is not used as a ranking control.

KB search should not fabricate policy conclusions. It only returns retrieved
chunks and metadata.

## Result Shape

Each result must include:
- `document_id` as Playbook `kb_documents.id`,
- `kb_service_document_id`,
- `chunk_id`,
- `chunk_index`,
- `text`,
- `score`,
- `metadata.source_title`,
- `metadata.source_date`,
- `metadata.organization_id`,
- `metadata.source_type`,
- `metadata.source_summary` when the KB-service document has a summary,
- `metadata.visibility_policy`.

Conversation-file results must also include `metadata.conversation_id`,
`metadata.conversation_file_id`, and source locator metadata when available.

## Citation Support

Returned results must contain enough data for Playbook to create
`message_citations` rows. Citations should point to document/chunk identifiers
and source metadata; they should not require loading the original document binary.

## Failure Behavior

| Failure | Expected Behavior |
|---------|-------------------|
| KB service unavailable | Main backend returns graceful unsupported/retryable chat outcome |
| Embedding provider unavailable | Search returns retryable structured error |
| No results over threshold | Main backend declines policy/process answer when source support is required |
| Unready documents exist | Search excludes them |
| Deleted document vectors remain temporarily | Search filter must exclude them by status/metadata |
