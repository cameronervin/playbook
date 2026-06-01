
Debug a bug using the bug-squasher skill with Cursor Debug Mode.

Follow the skill at `.claude/skills/bug-squasher/SKILL.md` which includes:
- Hypothesis generation (5-7 ranked hypotheses before any code changes)
- Targeted instrumentation (logging statements to test specific hypotheses)
- Runtime data collection (user reproduces bug while logs are captured)
- Root cause analysis (identify divergence point from expected behavior)
- Minimal targeted fix (2-3 lines preferred over large refactors)
- Human-in-the-loop verification (confirm fix works, check for regressions)

Default prompt: Debug the reported issue using hypothesis-driven analysis. Generate multiple hypotheses, instrument code to test them, collect runtime data, identify root cause, apply minimal fix, and verify with user before removing instrumentation.
