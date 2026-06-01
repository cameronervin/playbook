"""
Sprint Progress Status Parser

Utilities for parsing implementation files and user stories to extract
sprint progress status information.
"""

import re
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Status(Enum):
    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    NOT_STARTED = "not_started"


@dataclass
class StoryStatus:
    story_id: str
    description: str
    status: Status
    phase: int
    category: str = "unknown"


@dataclass
class UserStory:
    story_id: str
    description: str
    example: str
    category: str


def parse_status_marker(marker: str) -> Status:
    """Parse status marker from implementation file."""
    marker = marker.strip()
    if "✅" in marker:
        return Status.COMPLETED
    elif "☐" in marker:
        return Status.NOT_STARTED
    elif "[x]" in marker.lower():
        return Status.COMPLETED
    elif "[ ]" in marker:
        return Status.NOT_STARTED
    return Status.NOT_STARTED


def extract_story_ids(text: str) -> list[str]:
    """Extract user story IDs (US-X, TS-X) from text."""
    pattern = r"(US-\d+[a-z]?|TS-\d+)"
    return re.findall(pattern, text, re.IGNORECASE)


def parse_implementation_file(file_path: Path, phase_num: int) -> list[StoryStatus]:
    """
    Parse an implementation phase file and extract story statuses.
    
    Expected format:
    | Status | Goal | Relevant User Stories | ... |
    | ✅ | Description here | US-1, US-2 | ... |
    | ☐ | Another task | US-3 | ... |
    """
    results = []
    
    if not file_path.exists():
        return results
    
    content = file_path.read_text(encoding="utf-8")
    lines = content.split("\n")
    
    in_table = False
    header_found = False
    
    for line in lines:
        line = line.strip()
        
        if not line.startswith("|"):
            in_table = False
            header_found = False
            continue
        
        cells = [c.strip() for c in line.split("|")]
        cells = [c for c in cells if c]
        
        if len(cells) < 2:
            continue
        
        if "status" in cells[0].lower() or "---" in cells[0]:
            in_table = True
            header_found = "status" in cells[0].lower()
            continue
        
        if not in_table:
            continue
        
        status_cell = cells[0] if len(cells) > 0 else ""
        goal_cell = cells[1] if len(cells) > 1 else ""
        stories_cell = cells[2] if len(cells) > 2 else ""
        
        status = parse_status_marker(status_cell)
        story_ids = extract_story_ids(stories_cell)
        
        goal_text = re.sub(r"\*\*([^*]+)\*\*", r"\1", goal_cell)
        goal_text = goal_text.split("—")[0].strip() if "—" in goal_text else goal_text
        
        if story_ids:
            for story_id in story_ids:
                results.append(StoryStatus(
                    story_id=story_id.upper(),
                    description=goal_text[:100],
                    status=status,
                    phase=phase_num,
                ))
        elif goal_text:
            results.append(StoryStatus(
                story_id=f"P{phase_num}-TASK",
                description=goal_text[:100],
                status=status,
                phase=phase_num,
            ))
    
    return results


def parse_user_stories(file_path: Path) -> dict[str, UserStory]:
    """
    Parse user stories markdown file.
    
    Expected format:
    | ID | Story | Example |
    | US-1 | As a user, I want... | User does X |
    """
    stories = {}
    
    if not file_path.exists():
        return stories
    
    content = file_path.read_text(encoding="utf-8")
    lines = content.split("\n")
    
    current_category = "Unknown"
    in_table = False
    
    for line in lines:
        line_stripped = line.strip()
        
        if line_stripped.startswith("####"):
            current_category = line_stripped.replace("#", "").strip()
            in_table = False
            continue
        
        if not line_stripped.startswith("|"):
            in_table = False
            continue
        
        cells = [c.strip() for c in line_stripped.split("|")]
        cells = [c for c in cells if c]
        
        if len(cells) < 2:
            continue
        
        if cells[0].lower() == "id" or "---" in cells[0]:
            in_table = True
            continue
        
        if not in_table:
            continue
        
        story_id = cells[0].strip().upper()
        description = cells[1].strip() if len(cells) > 1 else ""
        example = cells[2].strip() if len(cells) > 2 else ""
        
        if re.match(r"^(US-\d+[a-z]?|TS-\d+)$", story_id, re.IGNORECASE):
            stories[story_id] = UserStory(
                story_id=story_id,
                description=description,
                example=example,
                category=current_category,
            )
    
    return stories


def aggregate_phase_statuses(
    implementation_dir: Path,
    phase_numbers: list[int],
) -> dict[int, list[StoryStatus]]:
    """
    Aggregate statuses from multiple phase files.

    Returns dict mapping phase number to list of story statuses.
    """
    results = {}
    safe_dir = Path(implementation_dir).resolve()
    _safe_root = Path.cwd().resolve()
    if not str(safe_dir).startswith(str(_safe_root)):
        raise ValueError(f"Implementation directory must be within the working directory: {_safe_root}")

    for phase_num in phase_numbers:
        file_path = safe_dir / f"phase-{phase_num}.md"
        statuses = parse_implementation_file(file_path, phase_num)
        results[phase_num] = statuses
    
    return results


def generate_summary(phase_statuses: dict[int, list[StoryStatus]]) -> dict:
    """Generate summary statistics from phase statuses."""
    total = 0
    completed = 0
    in_progress = 0
    not_started = 0
    
    for statuses in phase_statuses.values():
        for status in statuses:
            total += 1
            if status.status == Status.COMPLETED:
                completed += 1
            elif status.status == Status.IN_PROGRESS:
                in_progress += 1
            else:
                not_started += 1
    
    return {
        "total": total,
        "completed": completed,
        "in_progress": in_progress,
        "not_started": not_started,
    }


def format_status_for_table(status: Status) -> str:
    """Format status enum for markdown table display."""
    return {
        Status.COMPLETED: "Completed",
        Status.IN_PROGRESS: "In Progress",
        Status.NOT_STARTED: "Not Started",
    }.get(status, "Unknown")


def format_status_color(status: Status) -> str:
    """Get color name for status."""
    return {
        Status.COMPLETED: "green",
        Status.IN_PROGRESS: "blue",
        Status.NOT_STARTED: "white",
    }.get(status, "white")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python parse_status.py <implementation_dir> [phases]")
        print("Example: python parse_status.py implementation/ 1,2,3,4,5")
        sys.exit(1)
    
    impl_dir = Path(sys.argv[1])
    phases = [1, 2, 3, 4, 5]
    
    if len(sys.argv) > 2:
        phases = [int(p.strip()) for p in sys.argv[2].split(",")]
    
    phase_statuses = aggregate_phase_statuses(impl_dir, phases)
    summary = generate_summary(phase_statuses)
    
    print(f"Sprint Progress Summary")
    print(f"=======================")
    print(f"Total Items: {summary['total']}")
    print(f"Completed:   {summary['completed']}")
    print(f"In Progress: {summary['in_progress']}")
    print(f"Not Started: {summary['not_started']}")
    print()
    
    for phase_num, statuses in phase_statuses.items():
        print(f"\nPhase {phase_num}:")
        for s in statuses:
            print(f"  [{format_status_for_table(s.status)}] {s.story_id}: {s.description}")
