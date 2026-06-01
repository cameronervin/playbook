"""
Sprint Progress Infographic Generator

Generates sprint board images using the Gemini API that match
the corporate PPT slide format with phase columns and colored story boxes.

Supports two modes:
1. Overview: All 5 phases in one image (summary view)
2. Per-phase: Individual detailed images for each phase with full story details
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import date
from typing import Optional

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    print("Warning: google-genai not installed. Run: pip install google-genai")


def load_api_key(env_file: Optional[Path] = None) -> Optional[str]:
    """Load GEMINI_API_KEY from environment or .env file."""
    api_key = os.getenv("GEMINI_API_KEY")
    
    if api_key:
        return api_key
    
    env_paths = [
        env_file,
        Path(".env"),
        Path("backend/.env"),
        Path("../.env"),
    ]
    
    for env_path in env_paths:
        if env_path and env_path.exists():
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("GEMINI_API_KEY="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
    
    return None


def build_overview_prompt(phases_data: dict, title: str) -> str:
    """
    Build prompt for overview image showing all phases.
    """
    phase_summaries = []
    
    for phase_num in sorted(phases_data.keys()):
        stories = phases_data[phase_num]
        completed = sum(1 for s in stories if s.get("status") == "completed")
        in_progress = sum(1 for s in stories if s.get("status") == "in_progress")
        not_started = sum(1 for s in stories if s.get("status") == "not_started")
        total = len(stories)
        
        story_ids = [s.get("id", "") for s in stories[:8]]
        
        phase_summaries.append(f"""Phase {phase_num}:
    - Total: {total} stories
    - Completed (GREEN): {completed}
    - In Progress (BLUE): {in_progress}
    - Not Started (WHITE): {not_started}
    - Sample IDs: {', '.join(story_ids)}""")
    
    prompt = f"""Generate a professional sprint progress dashboard image matching this EXACT style:

VISUAL STYLE (CRITICAL - must match exactly):
- Background: Deep black/dark navy (#0a0a1a) with flowing, ethereal teal/cyan wave patterns
- The waves should be smooth, curved, luminescent lines flowing diagonally across the background
- Wave colors: Gradient from teal (#00b4d8) to cyan (#48cae4) with some pink/coral accents (#ff6b6b)
- The waves create an elegant, modern, premium corporate aesthetic

LAYOUT:
- Title "{title}" in white bold text, top-left, large font (like "Project - 2/18/26")
- Below title: A single white-bordered rectangular table spanning the width
- Table has 5 equal columns: "Phase 1", "Phase 2", "Phase 3", "Phase 4", "Phase 5"
- Column headers: Solid cyan/teal (#00b4d8) background bars with white text
- Thin white border (1-2px) around entire table and between columns
- Table background is semi-transparent or matches the dark background

STORY BOXES inside each column:
- Small rounded rectangle pills/boxes stacked vertically
- Each box shows the story ID (e.g., "US-12", "TS-5", "P1-TASK")
- Box colors by status:
  * DARK GREEN (#006644 or #065f46): Completed stories
  * CYAN/TEAL (#0077B6 or #0891b2): In Progress stories  
  * WHITE (#FFFFFF) with dark text: Not Started stories
- Boxes have small padding between them
- Text inside boxes should be readable (white text on colored, dark text on white)

PHASE DATA:
{chr(10).join(phase_summaries)}

IMPORTANT REQUIREMENTS:
- 16:9 widescreen aspect ratio (1920x1080 style)
- The flowing wave background is essential - it creates the premium look
- Story boxes must show actual IDs, not placeholder text
- Clean, minimal, executive presentation quality
- High contrast for readability

Generate this as a polished corporate infographic suitable for an executive presentation."""

    return prompt


def build_phase_detail_prompt(phase_num: int, stories: list, title: str) -> str:
    """
    Build prompt for detailed single-phase image with all stories visible.
    """
    completed_stories = []
    in_progress_stories = []
    not_started_stories = []
    
    for story in stories:
        status = story.get("status", "not_started")
        story_id = story.get("id", "")
        desc = story.get("description", "")[:40]
        
        entry = f"{story_id}: {desc}"
        
        if status == "completed":
            completed_stories.append(entry)
        elif status == "in_progress":
            in_progress_stories.append(entry)
        else:
            not_started_stories.append(entry)
    
    prompt = f"""Generate a professional sprint progress detail image for Phase {phase_num} matching this EXACT style:

VISUAL STYLE (CRITICAL - must match exactly):
- Background: Deep black/dark navy (#0a0a1a) with flowing, ethereal teal/cyan wave patterns
- The waves should be smooth, curved, luminescent lines flowing diagonally across the background
- Wave colors: Gradient from teal (#00b4d8) to cyan (#48cae4) with some pink/coral accents
- Creates an elegant, modern, premium corporate aesthetic

LAYOUT:
- Title "{title}" in white bold text, top-left corner
- Subtitle "Phase {phase_num} Details" below the title
- Main content area: White-bordered container with 3 columns

THREE COLUMNS (Status Categories):
1. "COMPLETED" column - Header: Dark green (#065f46) bar with white text
2. "IN PROGRESS" column - Header: Cyan/teal (#0891b2) bar with white text  
3. "NOT STARTED" column - Header: Gray (#6b7280) bar with white text

STORY CARDS in each column:
- Each story is a card/box showing: Story ID and brief description
- Cards stacked vertically within their column
- Card styling:
  * Completed: Dark green (#065f46) background, white text
  * In Progress: Cyan (#0891b2) background, white text
  * Not Started: White background, dark text
- Small gap between cards
- Text must be legible - use appropriate font size

COMPLETED STORIES ({len(completed_stories)} items):
{chr(10).join(f'- {s}' for s in completed_stories) if completed_stories else '- None'}

IN PROGRESS STORIES ({len(in_progress_stories)} items):
{chr(10).join(f'- {s}' for s in in_progress_stories) if in_progress_stories else '- None'}

NOT STARTED STORIES ({len(not_started_stories)} items):
{chr(10).join(f'- {s}' for s in not_started_stories) if not_started_stories else '- None'}

IMPORTANT:
- 16:9 widescreen aspect ratio
- The flowing wave background is essential for the premium look
- ALL story IDs and descriptions must be visible and readable
- Executive presentation quality
- If many stories, use smaller font but keep readable

Generate this as a polished corporate infographic."""

    return prompt


def generate_image(prompt: str, output_path: str, api_key: str) -> bool:
    """Generate a single image from prompt."""
    try:
        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model="gemini-3-pro-image-preview",
            contents=[prompt],
        )

        for part in response.parts:
            if part.inline_data is not None:
                image = part.as_image()

                safe_output = Path(output_path).resolve()
                _safe_root = Path.cwd().resolve()
                if not str(safe_output).startswith(str(_safe_root)):
                    print(f"Error: Output path must be within the working directory: {_safe_root}")
                    return False
                safe_output.parent.mkdir(parents=True, exist_ok=True)

                image.save(str(safe_output))
                print(f"Image saved to: {safe_output}")
                return True
        
        print("Warning: No image generated in response")
        if hasattr(response, 'text') and response.text:
            print(f"Response text: {response.text[:500]}")
        return False
        
    except Exception as e:
        print(f"Error generating image: {e}")
        return False


def generate_infographic(
    phases_data: dict,
    output_path: str,
    title: Optional[str] = None,
    api_key: Optional[str] = None,
    per_phase: bool = False,
) -> bool:
    """
    Generate sprint progress infographic(s) using Gemini API.
    
    Args:
        phases_data: Dict mapping phase numbers to lists of story dicts
        output_path: Path to save the generated image(s)
        title: Optional title (defaults to "Sprint Progress - {date}")
        api_key: Optional API key (will try to load from env if not provided)
        per_phase: If True, generate individual images for each phase
    
    Returns:
        True if successful, False otherwise
    """
    if not GENAI_AVAILABLE:
        print("Error: google-genai package not available")
        return False
    
    if not api_key:
        api_key = load_api_key()
    
    if not api_key:
        print("Error: GEMINI_API_KEY not found in environment or .env file")
        return False
    
    if not title:
        title = f"Project - {date.today().strftime('%-m/%d/%y')}"

    safe_output = Path(output_path).resolve()
    _safe_root = Path.cwd().resolve()
    if not str(safe_output).startswith(str(_safe_root)):
        print(f"Error: Output path must be within the working directory: {_safe_root}")
        return False
    safe_output.parent.mkdir(parents=True, exist_ok=True)

    success = True

    overview_prompt = build_overview_prompt(phases_data, title)
    if not generate_image(overview_prompt, str(safe_output), api_key):
        success = False

    if per_phase:
        for phase_num in sorted(phases_data.keys()):
            stories = phases_data[phase_num]
            if not stories:
                continue

            phase_prompt = build_phase_detail_prompt(phase_num, stories, title)
            phase_path = str((safe_output.parent / f"phase-{phase_num}-detail.png").resolve())
            
            if not generate_image(phase_prompt, phase_path, api_key):
                success = False
    
    return success


def generate_from_parse_status(
    implementation_dir: str,
    output_path: str,
    phases: list[int] = None,
    title: Optional[str] = None,
    per_phase: bool = False,
) -> bool:
    """
    Generate infographic by parsing implementation files directly.
    """
    script_dir = Path(__file__).parent
    sys.path.insert(0, str(script_dir))
    
    from parse_status import (
        aggregate_phase_statuses,
        Status,
    )
    
    if phases is None:
        phases = [1, 2, 3, 4, 5]
    
    impl_path = Path(implementation_dir).resolve()
    _safe_root = Path.cwd().resolve()
    if not str(impl_path).startswith(str(_safe_root)):
        print(f"Error: Implementation directory must be within the working directory: {_safe_root}")
        return False
    phase_statuses = aggregate_phase_statuses(impl_path, phases)
    
    phases_data = {}
    for phase_num, statuses in phase_statuses.items():
        phases_data[phase_num] = [
            {
                "id": s.story_id,
                "description": s.description,
                "status": s.status.value,
            }
            for s in statuses
        ]
    
    return generate_infographic(phases_data, output_path, title, per_phase=per_phase)


def main():
    parser = argparse.ArgumentParser(
        description="Generate sprint progress infographic using Gemini API"
    )
    parser.add_argument(
        "--output", "-o",
        default=f"docs/sprint-reports/{date.today().isoformat()}/sprint-progress.png",
        help="Output path for the generated image"
    )
    parser.add_argument(
        "--data", "-d",
        help="JSON string with phases data, or path to JSON file"
    )
    parser.add_argument(
        "--implementation-dir", "-i",
        help="Path to implementation directory (alternative to --data)"
    )
    parser.add_argument(
        "--phases", "-p",
        default="1,2,3,4,5",
        help="Comma-separated list of phase numbers"
    )
    parser.add_argument(
        "--title", "-t",
        help="Title for the infographic"
    )
    parser.add_argument(
        "--api-key", "-k",
        help="Gemini API key (or set GEMINI_API_KEY env var)"
    )
    parser.add_argument(
        "--per-phase",
        action="store_true",
        help="Generate individual detailed images for each phase"
    )
    
    args = parser.parse_args()
    
    phases = [int(p.strip()) for p in args.phases.split(",")]
    
    if args.implementation_dir:
        success = generate_from_parse_status(
            args.implementation_dir,
            args.output,
            phases,
            args.title,
            args.per_phase,
        )
    elif args.data:
        data_path = Path(args.data).resolve()
        _safe_root = Path.cwd().resolve()
        if not str(data_path).startswith(str(_safe_root)):
            parser.error(f"Data path must be within the working directory: {_safe_root}")
        if data_path.exists():
            with open(data_path, "r") as f:
                phases_data = json.load(f)
        else:
            phases_data = json.loads(args.data)
        
        int_phases_data = {int(k): v for k, v in phases_data.items()}
        
        success = generate_infographic(
            int_phases_data,
            args.output,
            args.title,
            args.api_key,
            args.per_phase,
        )
    else:
        print("Error: Must provide either --data or --implementation-dir")
        parser.print_help()
        sys.exit(1)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
