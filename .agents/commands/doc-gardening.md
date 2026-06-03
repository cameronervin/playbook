
Run documentation health check using the doc-gardening skill.

Follow the skill at `.claude/skills/doc-gardening/SKILL.md` which includes:
- Staleness detection (docs not updated recently, outdated content)
- Gap identification (new features without docs, missing API docs)
- Cross-reference verification (AGENTS.md matches folders, ADRs reflect decisions)
- Fix-up proposal generation (prioritized list of documentation fixes)

Default prompt: Scan the documentation for staleness, gaps, and inaccuracies. Generate a prioritized report of issues found and propose fixes.
