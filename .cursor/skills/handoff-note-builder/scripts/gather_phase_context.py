#!/usr/bin/env python3
"""
gather_phase_context.py

Helper for the handoff-note-builder skill. Reads the `backstage/prd/03-implementation/`
folder of a product codebase to identify the currently active phase and
surface the items under it, so Claude can reference concrete action items
from the plan when drafting the note.

Usage:
    python gather_phase_context.py [--repo <path>] [--phase <N>]

Arguments:
    --repo <path>   Path to the product repo root. Defaults to the current
                    working directory. The script looks for
                    <repo>/backstage/prd/03-implementation/ inside this path.
    --phase <N>     Force a specific phase number to load (e.g. --phase 5).
                    If omitted, the script infers the active phase from
                    file modification times (most recent phase file wins,
                    ignoring the top-level _implementation-plan.md).

Output:
    Prints a JSON document to stdout with:
    - active_phase_number
    - active_phase_file
    - active_phase_title
    - active_phase_summary (first ~40 lines or the Intro section, whichever comes first)
    - all_phase_files (list of every phase markdown found, for reference)
    - index_file_snippet (first ~30 lines of _implementation-plan.md if present)

    If the folder is not found, prints an error JSON with a hint the skill
    uses to fall back to asking the author directly for phase context.

This script is intentionally lightweight and read-only. It does not modify
any files and does not require any non-stdlib dependencies.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path


PHASE_FILE_PATTERN = re.compile(r"^phase-(\d+)[-_].*\.md$", re.IGNORECASE)
INDEX_FILE_CANDIDATES = ("_implementation-plan.md", "implementation-plan.md")


def find_implementation_dir(repo_root: Path) -> Path | None:
    """Locate the implementation folder. Tries the canonical path first,
    then a shallow search so the skill works even when the folder moves."""
    canonical = repo_root / "backstage" / "prd" / "03-implementation"
    if canonical.is_dir():
        return canonical

    # Shallow fallback: look for any dir matching "*implementation*"
    for candidate in repo_root.glob("**/03-implementation"):
        if candidate.is_dir():
            return candidate

    for candidate in repo_root.glob("**/implementation"):
        if candidate.is_dir() and candidate.parent.name.startswith("prd"):
            return candidate

    return None


def list_phase_files(impl_dir: Path) -> list[dict]:
    """Enumerate phase markdown files with their phase number and mtime."""
    results = []
    for f in sorted(impl_dir.iterdir()):
        if not f.is_file() or not f.suffix.lower() == ".md":
            continue
        m = PHASE_FILE_PATTERN.match(f.name)
        if not m:
            continue
        results.append({
            "file": str(f),
            "name": f.name,
            "phase_number": int(m.group(1)),
            "mtime": f.stat().st_mtime,
        })
    return results


def find_index_file(impl_dir: Path) -> Path | None:
    for candidate in INDEX_FILE_CANDIDATES:
        p = impl_dir / candidate
        if p.is_file():
            return p
    return None


def read_head(path: Path, max_lines: int = 40) -> str:
    """Read up to max_lines of the file or until the first 'Phase N:'-style
    section heading after the intro, whichever comes first."""
    lines = []
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh):
            if i >= max_lines:
                break
            lines.append(line.rstrip("\n"))
    return "\n".join(lines)


def extract_title(path: Path) -> str:
    """Pull the first # heading from a markdown file, if present."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("#"):
                    return line.lstrip("#").strip()
    except OSError:
        pass
    return ""


def pick_active_phase(phase_files: list[dict], forced_phase: int | None) -> dict | None:
    if not phase_files:
        return None
    if forced_phase is not None:
        for pf in phase_files:
            if pf["phase_number"] == forced_phase:
                return pf
        # If forced phase not found, fall through to default logic
    # Heuristic: the phase file most recently modified is the active one.
    # This tracks the author's habit of amending the current phase markdown
    # as work progresses. If mtimes are all identical (fresh checkout),
    # fall back to the highest phase number present.
    mtimes = {pf["mtime"] for pf in phase_files}
    if len(mtimes) > 1:
        return max(phase_files, key=lambda pf: pf["mtime"])
    return max(phase_files, key=lambda pf: pf["phase_number"])


def build_output(repo_root: Path, forced_phase: int | None) -> dict:
    impl_dir = find_implementation_dir(repo_root)
    if impl_dir is None:
        return {
            "status": "not_found",
            "error": (
                f"Could not find an implementation folder under {repo_root}. "
                "Expected backstage/prd/03-implementation/. "
                "Fall back: ask the author which phase they're in and what the "
                "priority items are."
            ),
        }

    phase_files = list_phase_files(impl_dir)
    if not phase_files:
        return {
            "status": "empty",
            "implementation_dir": str(impl_dir),
            "error": (
                "Found the implementation folder but no phase-*.md files in it. "
                "Fall back: ask the author for the relevant phase content."
            ),
        }

    active = pick_active_phase(phase_files, forced_phase)
    index_file = find_index_file(impl_dir)

    return {
        "status": "ok",
        "implementation_dir": str(impl_dir),
        "active_phase_number": active["phase_number"],
        "active_phase_file": active["file"],
        "active_phase_title": extract_title(Path(active["file"])) or active["name"],
        "active_phase_summary": read_head(Path(active["file"]), max_lines=50),
        "all_phase_files": [
            {
                "phase_number": pf["phase_number"],
                "file": pf["file"],
                "title": extract_title(Path(pf["file"])) or pf["name"],
            }
            for pf in sorted(phase_files, key=lambda x: x["phase_number"])
        ],
        "index_file_snippet": (
            read_head(index_file, max_lines=30) if index_file else None
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        default=os.getcwd(),
        help="Path to the product repo root (defaults to current working directory).",
    )
    parser.add_argument(
        "--phase",
        type=int,
        default=None,
        help="Force a specific phase number to load.",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo).expanduser().resolve()
    output = build_output(repo_root, args.phase)
    print(json.dumps(output, indent=2))
    return 0 if output.get("status") == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
