# Eval datasets

One YAML file per agent, named after the spec (e.g. `example.yaml`). Each file is
a list of items.

The harness mirrors these into Langfuse via an idempotent sync
(`python -m evals.cli sync-datasets`). A stable id is derived from each item's
`input`, so re-syncing upserts rather than duplicates.

## Item shape

```yaml
- input:
    question: "Summarize the key points of the provided context."
    # Optional extra keys are passed straight into the chain's state (e.g. any
    # upstream artifacts or documents your chain expects).
  expected_output: "A concise reference answer / structure the judge compares against."
  metadata:
    id: "example-summary-001"
    category: general
- input:
    question: "..."
  expected_output: "..."
  metadata:
    id: "example-summary-002"
    category: general
# ... more items
```

- `input` MUST contain one prompt field: `question`, `query`, or `prompt`. Any
  other keys under `input` flow into the chain state.
- `expected_output` is opaque to Langfuse; the judges decide how to use it
  (the LLM judge compares against it; Ragas uses it as `reference`).
- `metadata.id` is required and must be unique within the file. Use a stable,
  human-readable case id so reports and sync logs point to one case.
- `metadata.category` is required and drives release-readiness coverage checks.
- Top-level item keys are limited to `input`, `expected_output`, and `metadata`;
  put chain-specific state under `input`.

For Playbook release gates, these dataset names have required category minimums:

- `athlete_chat`: `nil`, `compliance`, `process`, `unknown`, `conflict`,
  `emergency`, `sensitive`
- `admin_chat`: `analytics_summary`, `dashboard_insights`,
  `authorized_records`, `out_of_scope`
- `dashboard_insights`: `nil`, `compliance`, `recruiting`, `unanswered`

## Shared KB source fixtures

Retrieval and citation evals use a shared, redacted KB fixture file at
`datasets/_fixtures/playbook_kb_sources.yaml`. Keep at least 18 source
fixtures in that file with `id`, `title`, and `content` (or equivalent
`body`/`text`) so offline validation can confirm the golden sets have source
material before any Langfuse sync.

## Offline validation

Validate datasets locally before syncing or running them:

```bash
cd backend
uv run --group evals python -m evals.cli validate-datasets
```

Validation checks YAML shape, required item fields, duplicate `metadata.id`
values, required category minimums, the shared KB fixture minimum, and forbidden
sensitive field names such as emails, phone numbers, passwords, tokens, API
keys, athlete names, and raw student/athlete IDs.

## Building from a CSV snapshot

The shipped `example.yaml` is hand-authored. A product can instead generate a
dataset from a CSV export of production records — see `../scripts/README.md` for
the recommended pattern (CSV snapshot → hydrate `item.input` → redact PII → write
`datasets/<name>.yaml`). That builder is domain-specific and intentionally not
shipped with the scaffold.

## Oversized inputs

If an item's `input` exceeds Langfuse's 1MB per-item limit, sync externalizes the
largest non-prompt field to a sidecar blob under `_blobs/` and stores a
`{"$blob_ref": ...}` placeholder. The chain adapter resolves the ref back to full
content before invoking the agent (see `evals/core/sync.py`).
