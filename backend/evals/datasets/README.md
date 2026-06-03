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
  metadata: {category: general}
- input:
    question: "..."
  expected_output: "..."
# ... more items
```

- `input` MUST contain `question` (or `query`) — the adapter maps it to a
  `HumanMessage`. Any other keys under `input` flow into the chain state.
- `expected_output` is opaque to Langfuse; the judges decide how to use it
  (the LLM judge compares against it; Ragas uses it as `reference`).
- `metadata` is optional and free-form.

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
