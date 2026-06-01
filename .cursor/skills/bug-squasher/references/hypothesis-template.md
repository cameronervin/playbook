# Hypothesis Template

Use this template to document each hypothesis during debugging.

## Hypothesis Format

For each hypothesis, document:

```markdown
### Hypothesis [N]: [Brief Title]

**Statement:** [Clear statement of what might be wrong]

**Category:** [State Management | Timing | Data Flow | Environment | Edge Case | Security | Performance]

**Confidence:** [High | Medium | Low]

**Expected Behavior:**
[What should happen if code is working correctly]

**Actual Behavior:**
[What is happening instead]

**Diagnostic Approach:**
[How to verify this hypothesis - specific log placement, values to check]

**Log Statement:**
```[language]
[Exact logging code to add]
```

**Test Result:** [Confirmed | Refuted | Inconclusive]

**Evidence:**
[Log output or observations that prove/disprove this hypothesis]
```

## Example Hypotheses

### Example 1: State Not Updating

```markdown
### Hypothesis 1: React state not updating after API call

**Statement:** The component state is not being updated after the API response is received, causing stale data to display.

**Category:** State Management

**Confidence:** High

**Expected Behavior:**
After API call completes, `setData(response)` should update state and trigger re-render with new data.

**Actual Behavior:**
Component shows old data even after successful API call.

**Diagnostic Approach:**
Log the API response and state value immediately after setState call.

**Log Statement:**
```typescript
console.log('[DEBUG H1]', {
  apiResponse: response,
  stateBefore: data,
  timestamp: Date.now()
});
setData(response);
setTimeout(() => console.log('[DEBUG H1 after]', { stateAfter: data }), 0);
```

**Test Result:** Confirmed

**Evidence:**
Log shows `apiResponse` has new data but `stateAfter` still shows old value. Closure issue - `data` captured at render time.
```

### Example 2: Race Condition

```markdown
### Hypothesis 2: Race condition between two async operations

**Statement:** Two concurrent API calls are completing in unpredictable order, causing the wrong data to be displayed.

**Category:** Timing

**Confidence:** Medium

**Expected Behavior:**
Most recent request should always win, displaying its data.

**Actual Behavior:**
Sometimes older request data overwrites newer request data.

**Diagnostic Approach:**
Log request start time and completion time for each call, track which completes last.

**Log Statement:**
```typescript
const requestId = Date.now();
console.log('[DEBUG H2] request start', { requestId, query });
const response = await fetchData(query);
console.log('[DEBUG H2] request complete', { requestId, query, responseTime: Date.now() });
```

**Test Result:** Confirmed

**Evidence:**
Logs show request A (id: 1000) completes at 1500ms, request B (id: 1200) completes at 1400ms. B's data is overwritten by A's late response.
```

### Example 3: Null Reference

```markdown
### Hypothesis 3: Accessing property on null object

**Statement:** Code assumes an object exists but it's null in certain conditions, causing TypeError.

**Category:** Edge Case

**Confidence:** High

**Expected Behavior:**
`user.profile.name` returns the user's name string.

**Actual Behavior:**
TypeError: Cannot read property 'name' of null

**Diagnostic Approach:**
Log the full object chain before the failing access.

**Log Statement:**
```python
logger.debug("debug_h3_null_check",
    user=user,
    user_type=type(user).__name__,
    has_profile=hasattr(user, 'profile') if user else False,
    profile=getattr(user, 'profile', 'NO_ATTR'))
```

**Test Result:** Confirmed

**Evidence:**
Log shows `user={'id': 123, 'profile': None}` - profile is explicitly None, not missing.
```

## Hypothesis Categories

### State Management
- Stale state (closure capturing old value)
- State not updating (missing setState call)
- State updating wrong component
- Global state conflicts
- Cache returning stale data

### Timing
- Race conditions (async operations)
- Debounce/throttle issues
- Event ordering problems
- Timeout too short/long
- Animation timing conflicts

### Data Flow
- Wrong data passed to function
- Missing data transformation
- Type coercion issues
- Serialization/deserialization errors
- API contract mismatch

### Environment
- Missing environment variable
- Wrong configuration loaded
- Dependency version mismatch
- Platform-specific behavior
- Development vs production difference

### Edge Case
- Null/undefined handling
- Empty array/object
- Boundary values (0, -1, MAX_INT)
- Unicode/special characters
- Very long strings

### Security
- Authentication state incorrect
- Authorization check failing
- Token expired/invalid
- CORS issues
- CSP blocking resource

### Performance
- Memory leak
- Infinite loop
- N+1 query
- Blocking main thread
- Resource exhaustion

## Confidence Level Guidelines

| Level | Criteria |
|-------|----------|
| **High** | Symptoms strongly suggest this cause; similar bugs seen before; stack trace points here |
| **Medium** | Plausible cause; symptoms partially match; worth investigating |
| **Low** | Unlikely but possible; edge case; investigate if others ruled out |

## Test Result Definitions

| Result | Meaning | Next Step |
|--------|---------|-----------|
| **Confirmed** | Evidence proves this is the root cause | Proceed to fix |
| **Refuted** | Evidence proves this is NOT the cause | Move to next hypothesis |
| **Inconclusive** | Not enough data to determine | Add more logging, re-test |
