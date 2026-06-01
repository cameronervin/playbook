# Cleanup Checklist

Safe removal process for dead code and technical debt.

## Before Removing Anything

### 1. Search All References
- [ ] Search codebase for all usages
- [ ] Check imports in other files
- [ ] Check test files for references
- [ ] Check documentation for mentions

```bash
# Python
rg "function_name" --type py
rg "ClassName" --type py
rg "from.*import.*name" --type py

# TypeScript
rg "function_name" --type ts --type tsx
rg "import.*name" --type ts --type tsx
```

### 2. Check Dynamic Usage
- [ ] Search for getattr/setattr patterns
- [ ] Search for string-based function calls
- [ ] Check for reflection/introspection

```bash
# Python dynamic checks
rg "getattr.*['\"]name['\"]"
rg "__getattribute__|__getattr__"
rg "importlib\.import_module"
rg "eval|exec"
```

### 3. Check External Exposure
- [ ] Is this an API endpoint?
- [ ] Is this exported in `__init__.py` or `index.ts`?
- [ ] Is this documented for external use?
- [ ] Could external systems depend on this?

### 4. Check Version Control
- [ ] When was this last modified?
- [ ] Why was it added (check git blame)?
- [ ] Are there related changes that depend on it?

```bash
git log -p --follow -- path/to/file.py
git blame path/to/file.py
```

## Safe Removal Categories

### Safe to Remove Now

| Criteria | Action |
|----------|--------|
| No references found | Remove immediately |
| Only referenced in its own tests | Remove code and tests together |
| Commented out code | Remove (it's in git history) |
| Unused imports | Remove |
| Unused local variables | Remove |
| Dead feature flag code (flag removed) | Remove |

### Remove with Caution

| Criteria | Action |
|----------|--------|
| Referenced but deprecated | Add deprecation warning first |
| Used in tests only | Verify tests aren't needed |
| Old API version | Verify no external consumers |

### Defer Removal

| Criteria | Action |
|----------|--------|
| External consumers exist | Migration plan required |
| Part of public API | Deprecation period required |
| Complex dependencies | Incremental removal plan |

## Removal Process

### For Unused Code

1. **Verify unused:**
   ```bash
   rg "function_name" --type py
   # Should return only the definition
   ```

2. **Remove the code:**
   - Delete function/class/variable
   - Delete associated tests (if only testing this code)
   - Delete imports

3. **Run tests:**
   ```bash
   cd backend && pytest -v
   cd frontend && npm test
   ```

4. **Run linter:**
   ```bash
   cd backend && ruff check .
   cd frontend && npm run lint
   ```

### For Commented Code

1. **Verify it's truly dead:**
   - Is there a TODO to uncomment?
   - Is it behind a feature flag?

2. **Check git history:**
   ```bash
   git log -p -- path/to/file.py | grep -A 20 "removed_function"
   ```
   - The code is preserved in history if needed

3. **Remove the comments**

### For Deprecated Code

1. **Add deprecation warning:**
   ```python
   import warnings
   
   def old_function():
       warnings.warn(
           "old_function is deprecated, use new_function instead",
           DeprecationWarning,
           stacklevel=2
       )
       return new_function()
   ```

2. **Update documentation**

3. **Set removal date:**
   - Add to tech-debt-tracker.md
   - Remove after deprecation period

## Post-Removal Verification

- [ ] All tests pass
- [ ] No linter errors
- [ ] No type errors
- [ ] No runtime errors (manual smoke test)
- [ ] Documentation updated (if referenced)
- [ ] Tech debt tracker updated (if tracked there)

## Rollback Plan

If removal causes issues:

1. **Immediate:** `git revert <commit>`
2. **Document:** Add to tech-debt-tracker.md why removal failed
3. **Plan:** Create proper migration/deprecation plan

## Tech Debt Tracking

For items that can't be removed now, add to `docs/tech-debt-tracker.md`:

```markdown
| ID | Area | Description | Priority | Created | Owner |
|----|------|-------------|----------|---------|-------|
| TD-XXX | [Area] | [What needs cleanup] | P1/P2 | [Date] | [Name] |
```

## Cleanup Metrics

Track cleanup progress:

- Lines of code removed this sprint
- Unused dependencies removed
- Test coverage change
- Linter warnings eliminated
- Tech debt items resolved
