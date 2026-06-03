# Eval offline scripts

This directory is the home for offline tooling that produces eval artifacts
(dataset builders, calibration helpers, etc.).

## Dataset builder (intentionally omitted)

The source harness this scaffold is derived from shipped a
`build_datasets_from_csv.py` script that generated dataset YAMLs from a
production CSV export. That builder was deeply domain-specific — it hydrated
stored product artifacts into Pydantic models and redacted production PII — so it
is **not** included here. A consumer adds their own, following this pattern:

1. **CSV snapshot.** Export the relevant production tables to CSV into a
   gitignored `evals/data/` directory (one file per table).
2. **Hydrate `item.input`.** For each record, build the chain's input — the
   driver `question` plus any upstream artifacts your chain expects under
   `input`. Validate stored artifacts against your real schemas so a row only
   qualifies if it would also load cleanly at run time.
3. **Redact PII.** Run a focused scrub before writing: mask email addresses and
   phone-shaped numbers, and replace raw record UUIDs with a short stable hash so
   a committed row can't be traced back to a production record. This is a focused
   scrub, not full anonymization — the eval signal (e.g. document body text) is
   preserved on purpose.
4. **Write `datasets/<name>.yaml`.** Emit the sampled, redacted items as a YAML
   list in the dataset item shape (see `../datasets/README.md`). Commit the
   redacted datasets; keep the raw CSV export gitignored.

```text
evals/data/<table>.csv   (gitignored)        # step 1
        │
        ▼  hydrate + validate                # step 2
   item.input  ──►  redact PII               # step 3
        │
        ▼  sample + write                     # step 4
evals/datasets/<name>.yaml  (committed, redacted)
```

Wire the new script as a CLI under `evals/scripts/` and document its usage here.
