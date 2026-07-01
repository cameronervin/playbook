"""Persist run results to disk for review after each eval run.

Each run writes two sibling files into ``results_dir`` (default
``backend/evals/results/``, gitignored):

- ``<run_name>.json`` — machine-readable, for programmatic comparison/calibration.
- ``<run_name>.md``   — a human-readable summary table.

The directory and files are local artifacts only; nothing here touches Langfuse
(scores already go there via the runner). Filenames are derived from the run
name, which the runner makes unique per run.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from evals.core.types import RunResult

# Default location for persisted run artifacts (gitignored).
DEFAULT_RESULTS_DIR = Path(__file__).resolve().parents[1] / "results"

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_filename(run_name: str) -> str:
    """Make a run name safe to use as a filename stem (colons from ISO times, etc.)."""
    return _UNSAFE.sub("_", run_name).strip("_") or "run"


def _to_dict(result: RunResult, *, timestamp: str) -> dict:
    return {
        "agent": result.agent,
        "run_name": result.run_name,
        "timestamp": timestamp,
        "passed": result.passed,
        "metadata": result.metadata,
        "mean_scores": result.mean_scores,
        "failures": result.failures,
        "errors": result.errors,
        "per_item": [
            {"item_id": pi.item_id, "trace_id": pi.trace_id, "scores": pi.scores}
            for pi in result.per_item
        ],
    }


def _to_markdown(result: RunResult, *, timestamp: str) -> str:
    status = "PASS" if result.passed else "FAIL"
    lines = [
        f"# Eval run: {result.agent}",
        "",
        f"- **Run name:** {result.run_name}",
        f"- **When:** {timestamp}",
        f"- **Result:** {status}",
    ]
    if result.metadata:
        lines += ["", "## Metadata", ""]
        for key, value in sorted(result.metadata.items()):
            rendered = json.dumps(value, default=str, sort_keys=True)
            lines.append(f"- **{key}:** {rendered}")
    lines += ["", "## Mean scores", "", "| Criterion | Mean |", "| --- | --- |"]
    for name, val in sorted(result.mean_scores.items()):
        lines.append(f"| {name} | {val:.3f} |")
    if not result.mean_scores:
        lines.append("| _(none recorded)_ | — |")

    if result.failures:
        lines += ["", "## Threshold failures", ""]
        lines += [f"- {f}" for f in result.failures]

    if result.errors:
        lines += ["", "## Judging errors (isolated — run still completed)", ""]
        lines += [f"- {e}" for e in result.errors]

    if result.per_item:
        lines += ["", "## Per-item scores", ""]
        for pi in result.per_item:
            lines.append(f"### {pi.item_id}")
            if pi.trace_id:
                lines.append(f"_trace: {pi.trace_id}_")
            lines += ["", "| Criterion | Score | Reasoning |", "| --- | --- | --- |"]
            for crit, entry in sorted(pi.scores.items()):
                score = entry.get("score")
                reason = str(entry.get("reasoning", "")).replace("\n", " ").replace("|", "\\|")
                lines.append(f"| {crit} | {score} | {reason} |")
            lines.append("")

    lines.append("")
    return "\n".join(lines)


def write_run_result(
    result: RunResult, *, results_dir: Path | str = DEFAULT_RESULTS_DIR
) -> tuple[Path, Path]:
    """Write ``result`` as JSON + Markdown; return ``(json_path, md_path)``."""
    out_dir = Path(results_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).isoformat(timespec="seconds")
    stem = _safe_filename(result.run_name)
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"

    json_path.write_text(
        json.dumps(_to_dict(result, timestamp=timestamp), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    md_path.write_text(_to_markdown(result, timestamp=timestamp), encoding="utf-8")
    return json_path, md_path
