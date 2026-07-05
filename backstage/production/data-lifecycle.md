# Data Lifecycle

Last updated: July 2, 2026

## Status

This document is a production rollout template. Retention periods remain
placeholders until counsel or the institutional rollout owner approves them.
Do not mark the P1 data lifecycle gate complete until the approval fields below
are filled.

The policy aligns to the NIST Privacy Framework goal of managing privacy risk
through clear data governance, minimization, retention, and disposal practices.

## Data Classes

| Data class | Examples | Default handling |
|------------|----------|------------------|
| Account/session | SSO identity, role, app session rows, OAuth state. | Store only fields needed for authentication and authorization. |
| Athlete chat | Conversation messages, message metadata, citations, safety labels. | Use for athlete history, grounded support, safety, and anonymized analytics. |
| Conversation files | Athlete-uploaded originals, extraction status, private KB chunks. | Scope to owning conversation; do not promote into shared KB in MVP. |
| Admin KB | Department-approved documents, tags, collections, chunks, embeddings. | Use for grounded answers and admin document operations. |
| Admin analytics | Anonymized query snapshots, dashboard insights, admin chat history. | Exclude athlete names, emails, raw user IDs, provider subjects, teams, and storage keys. |
| Audit logs | Role changes, KB actions, manual insight runs, admin chat events. | Append-only operational evidence. |
| Evals | Golden datasets, result summaries, trace IDs, judge scores. | Keep generated result artifacts out of git unless explicitly redacted. |
| Operational telemetry | Logs, traces, Sentry events, scanner/workflow artifacts. | Scrub secrets, signed URLs, raw IPs, and athlete identity; approved Langfuse traces may retain prompt/source content for evaluation, but exported artifacts require privacy review. |

## Retention Table

| Data class | Proposed period | Owner approval | Counsel approval | Notes |
|------------|-----------------|----------------|------------------|-------|
| Account/session | `<TBD>` | `<name/date>` | `<name/date>` | Include session revocation and inactive-user handling. |
| Athlete chat | `<TBD>` | `<name/date>` | `<name/date>` | Must support deletion/export requirements per institution. |
| Conversation files | `<TBD>` | `<name/date>` | `<name/date>` | Include original objects, extracted text, chunks, and embeddings. |
| Admin KB | `<TBD>` | `<name/date>` | `<name/date>` | Retention may follow institution content governance. |
| Admin analytics | `<TBD>` | `<name/date>` | `<name/date>` | Preserve anonymization; avoid re-identification fields. |
| Audit logs | `<TBD>` | `<name/date>` | `<name/date>` | Balance compliance needs with data minimization. |
| Evals | `<TBD>` | `<name/date>` | `<name/date>` | Generated artifacts must be redacted before sharing. |
| Operational telemetry | `<TBD>` | `<name/date>` | `<name/date>` | Align with Sentry/Langfuse/provider retention settings. |

## Deletion

- Verify requester authority before deleting account, conversation, file, or KB
  records.
- Delete or anonymize related objects consistently across Postgres, S3/MinIO,
  KB-service tables, vectors, and derived summaries.
- Preserve legally required audit records only when approved and documented.
- Record deletion evidence as sanitized ticket IDs, row/object IDs, and command
  outcomes; do not commit raw data exports or object listings.

## Export

- Export only data the requester is authorized to receive.
- Redact secrets, signed URLs, internal storage keys, provider tokens, raw IPs,
  and unrelated user data.
- Include citation/source metadata only when it does not expose private storage
  paths or another athlete's scoped conversation file.
- Track export requester, approver, scope, date, and delivery method in the
  rollout evidence system.

## Audit-Log Retention

Audit logs are append-only operational records. Production retention period,
access scope, and deletion exceptions remain `<TBD>` pending counsel and
institution approval.

## Eval Dataset Redaction

- Golden datasets may include realistic wording but must not include real
  athlete identity, real private files, provider tokens, signed URLs, or raw
  production source text.
- Generated eval results stay under ignored result paths unless a release owner
  approves a redacted summary.
- Production-to-eval promotion requires explicit redaction review and ticketed
  approval.

## Production-to-Test Data

Do not copy production databases, object buckets, traces, prompts, or source
documents into local/dev/test environments. Use synthetic fixtures or approved
redacted samples with ticketed approval, owner, expiry, and disposal evidence.
