# Root Cause Checklist

Common bug categories and their typical symptoms, causes, and fixes.

## State Management Issues

### Symptoms
- UI shows stale/old data
- Changes don't persist
- Data reverts unexpectedly
- Different components show different values for same data

### Common Causes

| Cause | Description | Fix |
|-------|-------------|-----|
| Closure capture | Callback captures old state value | Use functional update: `setState(prev => ...)` |
| Missing dependency | useEffect doesn't re-run when needed | Add missing deps to dependency array |
| Stale cache | Cached data not invalidated | Invalidate cache on mutation |
| Optimistic update failure | Rollback not triggered on error | Add error handling with rollback |
| Global state conflict | Multiple sources of truth | Consolidate to single source |

### Diagnostic Questions
- When was the state last updated?
- What triggered the state update?
- Is the component re-rendering after state change?
- Is there a cache between the data source and UI?

---

## Race Conditions / Timing

### Symptoms
- Intermittent failures
- "Works sometimes"
- Different results on fast vs slow connections
- Order-dependent bugs

### Common Causes

| Cause | Description | Fix |
|-------|-------------|-----|
| Async race | Later request finishes before earlier one | Use request ID, cancel stale requests |
| Missing await | Async operation not awaited | Add await keyword |
| Event ordering | Events fire in unexpected order | Add explicit sequencing |
| Debounce/throttle | Too aggressive or missing | Adjust timing, add debounce |
| Concurrent mutation | Multiple writers to same resource | Add locking or queue |

### Diagnostic Questions
- What is the timing of the operations?
- Are there multiple async operations that could conflict?
- Does the bug reproduce under slow network conditions?
- Is there a request ID to correlate requests/responses?

---

## Null/Undefined Handling

### Symptoms
- TypeError: Cannot read property 'X' of null/undefined
- Blank/missing UI elements
- Silent failures

### Common Causes

| Cause | Description | Fix |
|-------|-------------|-----|
| Missing null check | Accessing property on null | Add optional chaining `?.` or guard |
| Async data not loaded | Accessing data before fetch completes | Add loading state check |
| Optional field assumed present | API returns null for optional field | Handle null case explicitly |
| Array index out of bounds | Accessing `arr[0]` on empty array | Check length first |
| Destructuring null | `const { x } = nullValue` | Add default or guard |

### Diagnostic Questions
- What is the actual value (null vs undefined vs missing)?
- When is the value populated?
- Is this an optional field in the API contract?
- What should happen when the value is missing?

---

## API Contract Mismatches

### Symptoms
- Data appears wrong or malformed
- Type errors at runtime
- Missing fields in response
- Unexpected 400/422 errors

### Common Causes

| Cause | Description | Fix |
|-------|-------------|-----|
| Schema drift | Frontend expects different shape than backend sends | Sync schemas, add validation |
| Enum mismatch | String value not in expected set | Update enum definitions |
| Date format | Different date serialization | Standardize on ISO 8601 |
| Nested object changes | Backend restructured response | Update frontend types |
| Required vs optional | Field optionality changed | Update null handling |

### Diagnostic Questions
- What does the API documentation say?
- What is the actual response payload?
- Have there been recent backend changes?
- Are the TypeScript/Pydantic types up to date?

---

## Cache Staleness

### Symptoms
- Old data displayed after update
- Changes visible after refresh but not immediately
- Inconsistent data across pages

### Common Causes

| Cause | Description | Fix |
|-------|-------------|-----|
| Missing invalidation | Cache not cleared after mutation | Add cache invalidation |
| TTL too long | Cached data expires too slowly | Reduce TTL |
| Wrong cache key | Different keys for same data | Normalize cache keys |
| Browser cache | HTTP caching stale response | Add cache-busting headers |
| CDN cache | Edge cache serving old content | Purge CDN cache |

### Diagnostic Questions
- Is caching enabled for this data?
- When was the cache last invalidated?
- What is the cache TTL?
- Is this browser cache, application cache, or CDN cache?

---

## Environment Differences

### Symptoms
- "Works on my machine"
- Bug only in production/staging
- Different behavior across browsers
- CI passes but local fails (or vice versa)

### Common Causes

| Cause | Description | Fix |
|-------|-------------|-----|
| Missing env var | Environment variable not set | Add to deployment config |
| Different config | Dev vs prod configuration differs | Audit config differences |
| Dependency version | Different package versions | Lock dependencies |
| Browser compatibility | Feature not supported in all browsers | Add polyfill or fallback |
| Database state | Different data in different environments | Seed consistent test data |

### Diagnostic Questions
- What environment does the bug occur in?
- Are all environment variables set correctly?
- What are the dependency versions?
- Is there environment-specific configuration?

---

## Dependency Version Conflicts

### Symptoms
- "Module not found" errors
- Type mismatches after update
- Deprecated API warnings becoming errors
- Peer dependency warnings

### Common Causes

| Cause | Description | Fix |
|-------|-------------|-----|
| Breaking change | Major version bump with API changes | Read changelog, update usage |
| Peer dependency | Incompatible peer dependency versions | Align versions |
| Transitive dependency | Nested dependency conflict | Use resolutions/overrides |
| Lock file drift | package-lock.json out of sync | Delete and regenerate |
| Multiple versions | Same package at different versions | Dedupe dependencies |

### Diagnostic Questions
- What version is installed vs expected?
- Were there recent dependency updates?
- Are there peer dependency warnings?
- Is the lock file committed and up to date?

---

## Authentication/Authorization

### Symptoms
- 401 Unauthorized errors
- 403 Forbidden errors
- User sees wrong data
- Actions fail for some users

### Common Causes

| Cause | Description | Fix |
|-------|-------------|-----|
| Token expired | JWT/session expired | Refresh token, re-authenticate |
| Missing token | Auth header not sent | Add auth interceptor |
| Wrong permissions | User lacks required role | Check role assignment |
| Tenant isolation | User accessing wrong tenant's data | Add tenant check |
| CORS blocking | Preflight request failing | Configure CORS headers |

### Diagnostic Questions
- Is the user authenticated?
- What permissions does the user have?
- Is the token valid and not expired?
- Are CORS headers configured correctly?

---

## Performance Issues

### Symptoms
- Slow page load
- UI freezing/janking
- High memory usage
- Timeouts

### Common Causes

| Cause | Description | Fix |
|-------|-------------|-----|
| N+1 queries | Loop making individual DB calls | Batch queries |
| Missing index | Query scanning full table | Add database index |
| Memory leak | Objects not garbage collected | Fix reference retention |
| Blocking main thread | Sync operation blocking UI | Move to worker/async |
| Over-fetching | Loading more data than needed | Add pagination, select fields |

### Diagnostic Questions
- What is the time/memory profile?
- Are there repeated database queries?
- Is there a memory growth pattern?
- What is blocking the main thread?

---

## Quick Reference: Symptom to Category

| Symptom | Likely Category |
|---------|-----------------|
| "Cannot read property of null" | Null/Undefined Handling |
| "Works sometimes" | Race Condition / Timing |
| Shows old data | State Management or Cache |
| 401/403 errors | Authentication/Authorization |
| "Works on my machine" | Environment Differences |
| Type mismatch at runtime | API Contract Mismatch |
| Slow/freezing UI | Performance Issues |
| After recent update | Dependency Version Conflicts |
