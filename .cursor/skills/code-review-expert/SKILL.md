
# Code Review Expert

Perform structured review of git changes focusing on SOLID, security, performance, and reliability. Default to review-only output unless user asks to implement changes.

## Severity Levels

| Level | Name | Description | Action |
|-------|------|-------------|--------|
| **P0** | Critical | Security vulnerability, data loss risk, correctness bug | Must block merge |
| **P1** | High | Logic error, significant SOLID violation, performance regression | Should fix before merge |
| **P2** | Medium | Code smell, maintainability concern, minor SOLID violation | Fix in this PR or create follow-up |
| **P3** | Low | Style, naming, minor suggestion | Optional improvement |

## Workflow

### 1) Preflight Context

```bash
git status -sb
git diff --stat
git diff
```

- Use `rg` to find related modules, usages, and contracts.
- Identify entry points, ownership boundaries, and critical paths (auth, payments, data writes, network).

**Edge cases:**
- **No changes**: Inform user, ask if they want to review staged changes or specific commit range.
- **Large diff (>500 lines)**: Summarize by file first, then review in batches.
- **Mixed concerns**: Group findings by logical feature.

### 2) SOLID + Architecture Smells

Check for [SOLID violations](references/solid-checklist.md):

- **SRP**: Overloaded modules with unrelated responsibilities
- **OCP**: Frequent edits to add behavior instead of extension points
- **LSP**: Subclasses that break expectations or require type checks
- **ISP**: Wide interfaces with unused methods
- **DIP**: High-level logic tied to low-level implementations

When proposing refactors, explain *why* it improves cohesion/coupling and outline minimal, safe split.

### 3) Removal Candidates

Check for [removal candidates](references/removal-plan.md):

- Unused, redundant, or feature-flagged off code
- Distinguish **safe delete now** vs **defer with plan**
- Provide follow-up plan with concrete steps

### 4) Security & Reliability Scan

Check for [security issues](references/security-checklist.md):

- XSS, injection (SQL/NoSQL/command), SSRF, path traversal
- AuthZ/AuthN gaps, missing tenancy checks
- Secret leakage or API keys in logs/env/files
- Rate limits, unbounded loops, CPU/memory hotspots
- **Race conditions**: concurrent access, check-then-act, TOCTOU, missing locks

### 5) Code Quality Scan

Check for [code quality issues](references/code-quality-checklist.md):

- **Error handling**: swallowed exceptions, overly broad catch, missing error handling
- **Performance**: N+1 queries, CPU-intensive ops in hot paths, missing cache
- **Boundary conditions**: null/undefined handling, empty collections, off-by-one

### 6) Output Format

```markdown
## Code Review Summary

**Files reviewed**: X files, Y lines changed
**Overall assessment**: [APPROVE / REQUEST_CHANGES / COMMENT]

---

## Findings

### P0 - Critical
(none or list)

### P1 - High
- **[file:line]** Brief title
  - Description of issue
  - Suggested fix

### P2 - Medium
...

### P3 - Low
...

---

## Removal/Iteration Plan
(if applicable)

## Additional Suggestions
(optional improvements, not blocking)
```

**Clean review**: If no issues found, state what was checked and any areas not covered.

### 7) Next Steps

After presenting findings:

```markdown
---

## Next Steps

I found X issues (P0: _, P1: _, P2: _, P3: _).

**How would you like to proceed?**

1. **Fix all** - I'll implement all suggested fixes
2. **Fix P0/P1 only** - Address critical and high priority issues
3. **Fix specific items** - Tell me which issues to fix
4. **No changes** - Review complete, no implementation needed
```

**Important**: Do NOT implement changes until user explicitly confirms.

## Resources

For detailed checklists, see [references/](references/):
- `solid-checklist.md` - SOLID smells and refactor heuristics
- `security-checklist.md` - Security and runtime risk checklist
- `code-quality-checklist.md` - Error handling, performance, boundaries
- `removal-plan.md` - Deletion candidates and follow-up template
