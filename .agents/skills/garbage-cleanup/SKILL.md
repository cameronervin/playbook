
# Garbage Cleanup

Scan the codebase for dead code, AI-generated slop, and architectural drift. Inspired by OpenAI's Harness Engineering principle: "Technical debt is like a high-interest loan - it's almost always better to pay it down continuously."

## When to Use

- End of sprint cleanup
- Before major releases
- When codebase feels "messy"
- After rapid feature development
- When noticing inconsistent patterns

## Philosophy

Agents replicate patterns that exist in the repository—even uneven or suboptimal ones. Over time, this leads to drift. This skill encodes "golden principles" and scans for deviations.

## Workflow

### 1) Scan for Removal Candidates

**Unused imports:**
```bash
# Python - find unused imports
cd backend && ruff check . --select F401

# TypeScript - find unused imports
cd frontend && npx eslint . --rule "no-unused-vars: error"
```

**Unused functions and variables:**
```bash
# Python - find unused variables
cd backend && ruff check . --select F841

# Search for functions with no callers
rg "def function_name" --files-with-matches
rg "function_name\(" --files-with-matches
# Compare counts - if defined but never called, it's unused
```

**Dead code behind feature flags:**
```bash
# Find feature flag references
rg "feature_flag|FEATURE_" backend/
rg "featureFlag|FEATURE_" frontend/

# Check if any are always false/disabled
```

**Commented-out code blocks:**
```bash
# Find large commented blocks (Python)
rg "^#.*\n#.*\n#.*\n#" backend/ -l

# Find large commented blocks (TypeScript)
rg "^//.*\n//.*\n//" frontend/ -l
rg "/\*[\s\S]*?\*/" frontend/ -l
```

**Duplicate implementations:**
```bash
# Look for similar function names
rg "def (get|create|update|delete)_\w+" backend/ -o | sort | uniq -d

# Look for copy-paste patterns (same logic in multiple places)
```

### 2) Detect AI Slop Patterns

AI-generated code often exhibits these patterns. See [references/code-smell-patterns.md](references/code-smell-patterns.md) for details.

**Overly verbose code:**
- Functions that could be one-liners spread across 10+ lines
- Excessive comments stating the obvious
- Redundant null checks

**Inconsistent patterns:**
```bash
# Same operation done different ways
rg "async def" backend/app/services/ -l  # Check for consistency
rg "await.*session" backend/ -A 2  # Check DB access patterns
```

**Hand-rolled utilities:**
- Custom date formatting instead of using standard libraries
- Manual JSON parsing instead of Pydantic
- Custom retry logic instead of tenacity

**Magic strings:**
```bash
# Find hardcoded strings that should be constants
rg '"error":|"success":|"pending":|"completed":' backend/
rg "'error':|'success':|'pending':|'completed':" backend/
```

### 3) Check Architectural Drift

**Layer boundary violations:**
```bash
# Routes importing repositories directly (should go through services)
rg "from app.repositories" backend/app/api/ -l

# Services importing route definitions
rg "from app.api" backend/app/services/ -l

# Frontend components importing from wrong layers
rg "from.*repositories" frontend/src/components/ -l
```

**Dependencies in wrong direction:**
```bash
# Check import patterns follow the architecture:
# api/v1 → services → repositories → models

# Repositories should not import services
rg "from app.services" backend/app/repositories/ -l

# Models should not import anything from app (except other models)
rg "from app\.(api|services|repositories)" backend/app/models/ -l
```

**God classes/modules:**
```bash
# Find large files (potential god classes)
find backend/app -name "*.py" -exec wc -l {} + | sort -rn | head -20
find frontend/src -name "*.tsx" -exec wc -l {} + | sort -rn | head -20

# Files over 500 lines need review
```

### 4) Safe Removal Workflow

For each removal candidate, follow this process:

**Search all references:**
```bash
rg "function_name" --type py
rg "ClassName" --type py
```

**Check for dynamic/reflection usage:**
```bash
# Python - check for getattr, __getattribute__, etc.
rg "getattr.*['\"]function_name['\"]" backend/

# Check for string-based imports
rg "importlib|__import__" backend/
```

**Verify no external consumers:**
- Check API endpoints - is this exposed?
- Check exports - is this in `__init__.py` or `index.ts`?
- Check documentation - is this referenced?

**Categorize:**
- **Safe to remove now:** No references, not exposed, not documented
- **Defer with plan:** Has dependencies that need migration first

### 5) Output Report

```markdown
## Garbage Cleanup Report

**Scan Date:** [Date]
**Scope:** [backend/frontend/both]

---

### Safe to Remove Now

| Type | Location | Description | Impact |
|------|----------|-------------|--------|
| Unused import | `file.py:10` | `import unused_module` | None |
| Dead function | `file.py:50-75` | `def old_handler()` | None |
| Commented code | `file.py:100-150` | Old implementation | None |

### Defer Removal (Plan Required)

| Type | Location | Blocker | Plan |
|------|----------|---------|------|
| Deprecated API | `api/v1/old.py` | External consumers | Deprecation notice, remove in 30 days |

### AI Slop Detected

| Pattern | Location | Fix |
|---------|----------|-----|
| Magic strings | `service.py:45` | Extract to constants |
| Verbose code | `handler.py:20-40` | Simplify to 5 lines |
| Duplicate logic | `file1.py`, `file2.py` | Extract to shared utility |

### Architectural Drift

| Violation | Location | Fix |
|-----------|----------|-----|
| Route imports repository | `api/users.py:5` | Route through service |
| God class | `big_service.py` (800 lines) | Split by responsibility |

---

### Summary

- Items safe to remove: X
- Items requiring plan: X
- AI slop instances: X
- Architectural violations: X

### Recommended Actions

1. [First priority - quick wins]
2. [Second priority - medium effort]
3. [Third priority - needs planning]

### Add to Tech Debt Tracker

Items that can't be fixed immediately should be added to `docs/tech-debt-tracker.md`.
```

## Reference Documents

- [references/code-smell-patterns.md](references/code-smell-patterns.md) - Common AI slop patterns
- [references/cleanup-checklist.md](references/cleanup-checklist.md) - Safe removal checklist

## Golden Principles

These are the opinionated rules that keep the codebase consistent:

1. **Prefer shared utilities over hand-rolled helpers** - Keeps invariants centralized
2. **Validate boundaries, don't probe YOLO-style** - Use Pydantic/Zod, not runtime guessing
3. **One way to do each thing** - Consistency over personal preference
4. **Constants over magic strings** - Makes refactoring easier
5. **Small files over god classes** - 500 lines max, split by responsibility
6. **Layer boundaries are sacred** - api → services → repositories → models
