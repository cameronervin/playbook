
Run codebase cleanup scan using the garbage-cleanup skill.

Follow the skill at `.claude/skills/garbage-cleanup/SKILL.md` which includes:
- Unused code detection (imports, functions, variables, commented code)
- AI slop pattern identification (verbose code, inconsistent patterns, magic strings)
- Architectural drift checking (layer boundary violations, god classes)
- Safe removal recommendations (categorized as safe-now vs defer-with-plan)

Default prompt: Scan the codebase for dead code, AI slop patterns, and architectural drift. Generate a report with safe removal recommendations and items to add to tech debt tracker.
