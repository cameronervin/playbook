# KB Service Technical Docs

These documents define the KB service work required for the Playbook MVP. The
service is a standalone ingestion and retrieval system for admin-uploaded
department documents.

## Documents

| Document | Purpose |
|----------|---------|
| [architecture.md](architecture.md) | Service boundary, target flow, and required adaptations |
| [data-model.md](data-model.md) | KB-owned tables and durable content locations |
| [api-contracts.md](api-contracts.md) | Main backend to KB service API and webhook contracts |
| [ingestion-pipeline.md](ingestion-pipeline.md) | Parse, chunk, embed, load, retry, and deletion behavior |
| [retrieval.md](retrieval.md) | Search behavior, filtering, ranking metadata, and response shape |
| [operations-security.md](operations-security.md) | Service auth, secrets, observability, and failure handling |

## Boundary Summary

The main Playbook backend stores original admin-uploaded files and the
`kb_documents` control-plane row. The KB service stores searchable chunk text,
embedding vectors, ingestion logs, and service-local document state. Conversation
file uploads remain in the main backend and are not part of the shared KB corpus.
