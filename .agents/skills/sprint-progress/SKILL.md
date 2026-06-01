
# Sprint Progress Tracker

Generate sprint progress reports by analyzing implementation status against user stories.

## Output Modes

1. **Table**: Markdown table with story IDs, descriptions, and statuses
2. **Infographic**: AI-generated image matching PPT slide format via Gemini API

Reports saved to `docs/sprint-reports/YYYY-MM-DD/`.

## Configuration

On first run, confirm or update these defaults:

```yaml
# Default configuration (update paths for your project)
implementation_path: implementation/
user_stories_path: prd/05-user-stories.md
phases: [1, 2, 3, 4, 5]
```

If paths differ from defaults, ask user to provide correct paths and update this section.

## Workflow

### Step 1: Gather Configuration

Ask user using AskQuestion tool:

```
Question 1: "Confirm configuration paths"
Options:
- Use defaults (implementation/, prd/05-user-stories.md)
- Provide custom paths
```

If custom paths needed, ask for:
- Implementation files directory
- User stories file path
- Which phases to include

### Step 2: Scan Implementation Files

Read each phase file (e.g., `implementation/phase-1.md`, `implementation/phase-4.md`).

**Status Detection Rules:**

| Marker | Status | Color |
|--------|--------|-------|
| `\| ✅ \|` | Completed | Green |
| `\| ☐ \|` with activity | In Progress | Blue |
| `\| ☐ \|` no activity | Not Started | White |

For each row in implementation tables, extract:
- Status marker
- Goal/deliverable description
- Relevant user story IDs (e.g., US-31, TS-10)

### Step 3: Parse User Stories

Read user stories file and build lookup map:
- Story ID → Description
- Story ID → Category (Primary/Technical)

Cross-reference with implementation status.

### Step 4: Code Verification (Optional)

For claimed completions, optionally verify:
- Search codebase for related implementations
- Check for tests matching story requirements
- Flag discrepancies for review

### Step 5: Choose Output Format

Ask user using AskQuestion tool:

```
Question: "What output format would you like?"
Options:
- Table (markdown)
- Infographic (AI-generated image)
- Both
```

### Step 6: Generate Outputs

**For Table Output:**

Create `docs/sprint-reports/YYYY-MM-DD/sprint-progress.md` using template:

```markdown
# Sprint Progress Report - YYYY-MM-DD

## Summary
- Total Stories: X
- Completed: X (green)
- In Progress: X (blue)
- Not Started: X (white)

## Phase 1: [Phase Name]
| Status | Story ID | Description |
|--------|----------|-------------|
| Completed | US-1 | SSO login |
| Completed | US-2 | Home page layout |

## Phase 2: [Phase Name]
...
```

**For Infographic Output:**

1. Ensure `GEMINI_API_KEY` exists in environment (check `.env` file)
2. Run the infographic generation script with `--per-phase` flag (recommended):

```bash
python .Codex/skills/sprint-progress/scripts/generate_infographic.py \
  --implementation-dir implementation/ \
  --output "docs/sprint-reports/YYYY-MM-DD/sprint-progress.png" \
  --per-phase
```

This generates:
- `sprint-progress.png` - High-level overview showing all 5 phases with story counts and sample IDs
- `phase-1-detail.png` through `phase-5-detail.png` - Detailed views for each phase with ALL story IDs and descriptions

**Always use `--per-phase`** to get both the executive summary view and the detailed breakdowns.

### Step 7: Report Results

Display summary:
```
Sprint Progress Report Generated

Stories by Status:
- Completed: 32
- In Progress: 8
- Not Started: 8

Output Files:
- docs/sprint-reports/2026-02-18/sprint-progress.md
- docs/sprint-reports/2026-02-18/sprint-progress.png
```

## Scripts

### generate_infographic.py

Generates sprint board images via Gemini API using `gemini-3-pro-image-preview` model.

**Output (with `--per-phase` flag):**
1. `sprint-progress.png` - High-level overview with all 5 phases, story counts, and sample IDs
2. `phase-X-detail.png` - Detailed images for each phase with ALL story IDs and descriptions

**Recommended Usage:**
```bash
python .Codex/skills/sprint-progress/scripts/generate_infographic.py \
  --implementation-dir implementation/ \
  --output "docs/sprint-reports/YYYY-MM-DD/sprint-progress.png" \
  --per-phase
```

**Visual Style:**
- Dark background with flowing teal/cyan wave patterns
- White-bordered table with cyan header bars
- Story boxes: Green (completed), Cyan (in progress), White (not started)
- Executive presentation quality matching corporate PPT templates

**Requires:**
- `GEMINI_API_KEY` environment variable
- `google-genai` package
- `Pillow` package
- Model: `gemini-3-pro-image-preview` (hardcoded)

### parse_status.py

Utility functions for parsing implementation files. Import and use:

```python
from parse_status import parse_implementation_file, parse_user_stories
```

## Status Color Reference

| Status | Table Display | Infographic Color |
|--------|---------------|-------------------|
| Completed | `Completed` | Green (#006644) |
| In Progress | `In Progress` | Blue (#0077B6) |
| Not Started | `Not Started` | White (#FFFFFF) |

## Example Session

```
User: Generate sprint progress report

Agent: I'll generate a sprint progress report. Let me confirm your configuration:

1. Implementation files: `implementation/`
2. User stories: `prd/05-user-stories.md`
3. Phases: 1, 2, 3, 4, 5

[Uses AskQuestion to confirm]

Agent: What output format would you like?
- Table (markdown)
- Infographic (AI-generated image)
- Both

[User selects "Both"]

Agent: Scanning implementation files...

[Reads phase files, parses statuses]

Agent: Found 48 user stories across 5 phases:
- Completed: 32
- In Progress: 8
- Not Started: 8

Generating outputs...

[Creates directory, generates table, runs infographic script]

Agent: Sprint progress report generated:
- docs/sprint-reports/2026-02-18/sprint-progress.md
- docs/sprint-reports/2026-02-18/sprint-progress.png (overview)
- docs/sprint-reports/2026-02-18/phase-1-detail.png
- docs/sprint-reports/2026-02-18/phase-2-detail.png
- docs/sprint-reports/2026-02-18/phase-3-detail.png
- docs/sprint-reports/2026-02-18/phase-4-detail.png
- docs/sprint-reports/2026-02-18/phase-5-detail.png
```

## Troubleshooting

**Infographic generation fails:**
- Verify `GEMINI_API_KEY` is set in `.env`
- Check `google-genai` package is installed: `pip install google-genai`
- Ensure Pillow is installed: `pip install Pillow`

**Status detection incorrect:**
- Implementation files must use `| ✅ |` or `| ☐ |` markers in table format
- Verify table structure matches expected format

**Missing user stories:**
- Ensure user stories file uses `| US-X |` or `| TS-X |` ID format
- Check story IDs in implementation files match user stories file
