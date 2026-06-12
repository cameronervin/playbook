# KB Service Retrieval

This document defines semantic retrieval behavior for shared Playbook KB
documents.

## Search Scope

Search includes only admin-uploaded KB documents that are:
- successfully ingested,
- owned by the requested `organization_id`,
- not deleted or archived,
- visible to the requesting audience,
- in the configured Playbook collection.

Athlete conversation files are not searched by the KB service in MVP.

## Query Flow

1. Main backend receives an athlete chat message.
2. Chat orchestration decides whether KB retrieval is required.
3. Main backend calls KB service search with query, organization ID, limit, threshold, and visibility context.
4. KB service embeds the query.
5. KB service runs cosine similarity search against ready vectors.
6. KB service returns chunk text, score, document IDs, and metadata.
7. Main backend may re-rank or filter using safety policy and source date.
8. Assistant answer cites returned sources through `message_citations`.

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

## Ranking Signals

The KB service returns similarity score and metadata. Final answer orchestration
may combine:
- vector similarity score,
- `source_date`,
- freshness/conflict rules,
- safety/risk category.

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
- `metadata.visibility_policy`.

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
