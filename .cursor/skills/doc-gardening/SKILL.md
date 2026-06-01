
# Doc Gardening

Scan the codebase to ensure documentation remains accurate and up-to-date. Inspired by OpenAI's Harness Engineering principle: "A monolithic manual turns into a graveyard of stale rules."

## When to Use

- Periodic documentation health checks (weekly/sprint)
- Before major releases
- After significant refactoring
- When onboarding identifies doc gaps
- When docs seem out of sync with code

## Workflow

### 1) Scan for Staleness

Check documentation files for outdated content:

```bash
# Find docs not modified recently
find docs/ -name "*.md" -mtime +90 -type f

# Check AGENTS.md structure matches actual folders
ls -la docs/
ls -la prd/
ls -la implementation/
```

**Check each area:**

| Area | Verify |
|------|--------|
| `docs/architecture/overview.md` | Matches current system design |
| `docs/api/endpoints.md` | All endpoints documented, none missing |
| `docs/guides/setup.md` | Setup instructions still work |
| `AGENTS.md` | Folder structure matches reality |

**Compare code behavior to documented behavior:**

```bash
# List actual API endpoints
rg "router\.(get|post|put|delete|patch)" backend/app/api/ -l

# Compare to docs/api/endpoints.md
# Are all endpoints documented?
```

### 2) Identify Gaps

Look for missing documentation:

**New endpoints without API docs:**
```bash
# Find route definitions
rg "@router\." backend/app/api/v1/ -A 2

# Cross-reference with docs/api/endpoints.md
```

**New features without architecture updates:**
```bash
# Recent significant changes
git log --oneline --since="30 days ago" -- backend/app/services/
git log --oneline --since="30 days ago" -- backend/app/agents/

# Do these have corresponding docs?
```

**Changed behavior without ADRs:**
```bash
# List existing ADRs
ls docs/architecture/decisions/

# Were recent architectural changes documented?
```

### 3) Cross-Reference Verification

Verify consistency across documentation:

**AGENTS.md matches actual structure:**
- [ ] `docs/` folder structure accurate
- [ ] `prd/` folder structure accurate
- [ ] `implementation/` folder structure accurate
- [ ] Architecture diagram reflects current code
- [ ] Libraries list reflects actual dependencies

**ADRs reflect current decisions:**
```bash
# Read each ADR and verify it's still accurate
cat docs/architecture/decisions/*.md
```

**Setup guides work with current dependencies:**
```bash
# Check package versions match
cat backend/requirements.txt
cat frontend/package.json

# Do setup instructions reference correct versions?
```

### 4) Check for Dead Links

Find broken internal references:

```bash
# Find markdown links
rg "\[.*\]\(.*\.md\)" docs/ --only-matching

# Verify each linked file exists
```

### 5) Generate Fix-Up List

Categorize findings by priority:

| Priority | Category | Description |
|----------|----------|-------------|
| **P0** | Incorrect | Documentation contradicts actual behavior |
| **P1** | Missing | Functionality exists without documentation |
| **P2** | Stale | Documentation is outdated but not wrong |
| **P3** | Enhancement | Documentation could be clearer |

### 6) Output Report

```markdown
## Documentation Health Report

**Scan Date:** [Date]
**Files Scanned:** [Count]

---

### P0 - Incorrect (Must Fix)

| File | Issue | Fix Required |
|------|-------|--------------|
| `path/to/doc.md` | [Description] | [What to change] |

### P1 - Missing (Should Add)

| Missing Doc | For | Action |
|-------------|-----|--------|
| API endpoint doc | `POST /api/v1/xyz` | Add to endpoints.md |

### P2 - Stale (Update When Possible)

| File | Issue | Last Updated |
|------|-------|--------------|
| `path/to/doc.md` | [What's stale] | [Date] |

### P3 - Enhancements

- [List of improvement suggestions]

---

### Summary

- P0 Issues: X
- P1 Issues: X
- P2 Issues: X
- P3 Suggestions: X

### Recommended Actions

1. [First priority fix]
2. [Second priority fix]
3. [Third priority fix]
```

## Documentation Coverage Checklist

See [references/doc-coverage-checklist.md](references/doc-coverage-checklist.md) for detailed checklist.

## Automation Ideas

For recurring doc-gardening:

1. **CI check for doc freshness** - Warn on PRs that change code without updating relevant docs
2. **Link checker** - Automated broken link detection
3. **Structure validator** - Verify AGENTS.md matches actual folders
4. **API doc generator** - Auto-generate endpoint docs from code annotations
