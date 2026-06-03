# Eval run results

Each eval run (`python -m evals.cli run --agent <name>` or `run-all`) writes two
files here, named after the run:

- `<run_name>.json` — machine-readable: `agent`, `run_name`, `timestamp`,
  `passed`, `mean_scores`, `failures`, `errors`, `per_item`. Use for comparing
  runs over time and for threshold calibration.
- `<run_name>.md` — human-readable summary table (mean scores, threshold
  failures, isolated judging errors, and per-item scores).

`errors` lists per-item/per-rubric judging failures that were **isolated** — the
run completed anyway. A judge model rejecting an oversized prompt, for example,
records an error here instead of aborting the whole suite.

These files are **gitignored**: they embed mean scores and judge reasoning over
the datasets and are regenerated on every run. The `.gitkeep` and this README are
the only tracked files in the folder.
