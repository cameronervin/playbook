
# Bug Squasher

Systematic debugging workflow leveraging Cursor's Debug Mode. This skill guides through hypothesis-driven debugging with runtime instrumentation, following research-backed methodologies (DoVer intervention-driven debugging, TraceCoder trace-driven analysis).

## When to Use

- Bug reports with unclear root cause
- Errors that resist initial fix attempts
- Intermittent or flaky behavior
- Performance regressions
- User explicitly requests Debug Mode
- Standard agent fixes have failed

## Severity Levels

| Level | Name | Description | Action |
|-------|------|-------------|--------|
| **P0** | Critical | Crash, data loss, security breach | Drop everything, fix immediately |
| **P1** | High | Core functionality broken | Fix before other work |
| **P2** | Medium | Feature degraded, workaround exists | Fix in current session |
| **P3** | Low | Minor annoyance, cosmetic | Fix if time permits |

## Workflow

### 1) Preflight Context

Gather all available information about the bug:

```bash
# Check recent changes that might have introduced the bug
git log --oneline -10
git diff HEAD~5 --stat

# Look for related error logs
rg "error|Error|ERROR" --type py -C 2
rg "error|Error|ERROR" --type ts -C 2
```

**Collect from user:**
- Error message (exact text)
- Stack trace (if available)
- Steps to reproduce
- Expected vs actual behavior
- When it started (recent change? always broken?)
- Environment (local/dev/prod, browser, OS)

**Edge cases:**
- **No reproduction steps**: Ask user to describe what they were doing
- **Intermittent bug**: Ask for frequency, any patterns noticed
- **No error message**: Ask what behavior indicates the bug

### 2) Hypothesis Generation

Generate 5-7 hypotheses about the root cause. **Do NOT jump to fixing yet.**

Use [references/hypothesis-template.md](references/hypothesis-template.md) for structure.

**Hypothesis categories to consider:**
- State management (stale state, race condition, missing update)
- Data flow (wrong data passed, missing transformation)
- Timing (async ordering, debounce/throttle issues)
- Environment (config difference, missing dependency)
- Edge case (null handling, empty collection, boundary)

**Rank hypotheses by:**
1. Likelihood based on symptoms
2. Ease of verification
3. Severity if confirmed

Present hypotheses to user:

```markdown
## Hypotheses

Based on the symptoms, here are the most likely causes:

| # | Hypothesis | Confidence | Diagnostic |
|---|------------|------------|------------|
| 1 | [Most likely cause] | High | [How to verify] |
| 2 | [Second cause] | Medium | [How to verify] |
| 3 | [Third cause] | Medium | [How to verify] |
| ... | ... | ... | ... |

I'll instrument the code to test these. Please reproduce the bug when ready.
```

### 3) Instrumentation Plan

Design logging statements to test each hypothesis. Follow [references/instrumentation-patterns.md](references/instrumentation-patterns.md).

**Principles:**
- One log per hypothesis (minimal instrumentation)
- Log at decision points, not everywhere
- Include context: variable values, timestamps, request IDs
- Use structured logging format

**Python example:**
```python
import structlog
logger = structlog.get_logger(__name__)

# Hypothesis 1: User ID is null when it shouldn't be
logger.debug("debug_h1_user_check", user_id=user_id, expected="non-null")

# Hypothesis 2: Cache returns stale data
logger.debug("debug_h2_cache_check", cache_key=key, cached_value=cached, fresh_value=fresh)
```

**TypeScript example:**
```typescript
// Hypothesis 1: State not updating after API call
console.log('[DEBUG H1]', { action: 'api_response', data, stateAfter: state });

// Hypothesis 2: Event handler not firing
console.log('[DEBUG H2]', { event: 'click', target: e.target, timestamp: Date.now() });
```

### 4) Runtime Collection

**Instruct user:**

```markdown
## Ready to Collect Runtime Data

I've added diagnostic logging to test the hypotheses. Please:

1. **Reproduce the bug** by following your original steps
2. **Copy the console/terminal output** after the bug occurs
3. **Paste the logs here** so I can analyze them

If using Cursor Debug Mode, the logs will be collected automatically.
```

**Wait for user to provide logs before proceeding.**

### 5) Root Cause Analysis

Analyze the collected logs to identify the divergence point.

**Analysis steps:**
1. Match log entries to hypotheses
2. Identify which hypothesis is confirmed/refuted
3. Find the exact point where behavior diverges from expected
4. Trace back to the root cause

Use [references/root-cause-checklist.md](references/root-cause-checklist.md) to categorize.

**Present findings:**

```markdown
## Root Cause Analysis

### Logs Analysis

| Hypothesis | Result | Evidence |
|------------|--------|----------|
| H1: [description] | **Confirmed** | Log shows X when expected Y |
| H2: [description] | Refuted | Log shows correct value |
| H3: [description] | Inconclusive | Need more data |

### Root Cause

**Category:** [State Management / Timing / Data Flow / etc.]

**Location:** `path/to/file.py:123`

**Explanation:** [Clear explanation of why the bug occurs]

**Evidence:** [Specific log entries that prove this]
```

### 6) Targeted Fix

Apply a minimal, targeted fix. **Prefer 2-3 lines over large refactors.**

**Fix principles:**
- Address root cause, not symptoms
- Minimal change to reduce risk
- Preserve existing behavior for non-buggy paths
- Add defensive checks if appropriate

**Before implementing, explain the fix:**

```markdown
## Proposed Fix

**Change:** [Brief description]

**File:** `path/to/file.py`

**Rationale:** [Why this fixes the root cause]

**Risk:** [Low/Medium/High] - [Explanation]

Implementing now...
```

### 7) Verification

After applying the fix, request user verification.

```markdown
## Verification Required

I've applied the fix. Please:

1. **Reproduce the original steps** that caused the bug
2. **Confirm the bug is fixed** (expected behavior now occurs)
3. **Check for regressions** (other functionality still works)

Reply with:
- ✅ **Fixed** - Bug is resolved, no regressions
- ⚠️ **Partial** - Bug improved but not fully fixed
- ❌ **Not fixed** - Bug still occurs
- 🔄 **Regression** - New issue introduced
```

**After user confirms fix:**

1. Remove all diagnostic logging added in step 3
2. Run tests to ensure no regressions
3. Provide summary report

```bash
# Run tests
cd backend && pytest -v
cd frontend && npm test
```

## Output Format

After verification, provide final report:

```markdown
## Bug Fix Summary

**Bug:** [One-line description]
**Severity:** P[0-3]
**Status:** ✅ Fixed and Verified

### Root Cause

[Category]: [Brief explanation]

### Hypotheses Tested

| # | Hypothesis | Result |
|---|------------|--------|
| 1 | [H1] | Confirmed ✓ |
| 2 | [H2] | Refuted |
| 3 | [H3] | Refuted |

### Fix Applied

**File:** `path/to/file.py`
**Lines changed:** X

[Code snippet or description of change]

### Verification

- [x] User confirmed bug is fixed
- [x] No regressions observed
- [x] Diagnostic logging removed
- [x] Tests pass

### Lessons Learned

[Pattern to watch for in future, if applicable]
```

## Key Principles

1. **Reason before fixing** - Generate hypotheses first, never jump to code changes
2. **Minimal instrumentation** - Only add logs that test specific hypotheses
3. **Human verification** - Always ask user to confirm fix works
4. **Clean removal** - Remove all instrumentation after fix verified
5. **Historical learning** - Note patterns for future similar bugs
6. **Two-stage verification** - Hypothesize → validate, don't guess

## Anti-Patterns to Avoid

| Anti-Pattern | Do Instead |
|--------------|------------|
| Jump straight to fixing | Generate hypotheses first |
| Add logging everywhere | Target specific hypotheses |
| Large refactor as fix | Minimal targeted change |
| Skip user verification | Always confirm fix works |
| Leave debug logs in code | Remove after verification |
| Assume first hypothesis is correct | Test multiple hypotheses |

## Resources

- [references/hypothesis-template.md](references/hypothesis-template.md) - Structured hypothesis format
- [references/instrumentation-patterns.md](references/instrumentation-patterns.md) - Logging patterns by language
- [references/root-cause-checklist.md](references/root-cause-checklist.md) - Common bug categories
