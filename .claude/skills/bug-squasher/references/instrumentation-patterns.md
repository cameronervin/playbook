# Instrumentation Patterns

Language-specific logging patterns for hypothesis-driven debugging.

## General Principles

1. **Prefix all debug logs** with `[DEBUG H#]` to identify hypothesis being tested
2. **Include context** - variable values, timestamps, identifiers
3. **Log at decision points** - before/after conditionals, async boundaries
4. **Use structured format** - objects/dicts, not string concatenation
5. **Remove after verification** - search for `DEBUG` prefix to clean up

## Python Patterns

### Using structlog (Preferred)

```python
import structlog

logger = structlog.get_logger(__name__)

# Basic hypothesis check
logger.debug("debug_h1_check",
    hypothesis="user_id is null",
    user_id=user_id,
    expected="non-null value")

# Entry/exit logging
logger.debug("debug_h2_entry",
    function="process_order",
    order_id=order.id,
    items_count=len(order.items))

result = process_order(order)

logger.debug("debug_h2_exit",
    function="process_order",
    result_status=result.status,
    duration_ms=(time.time() - start) * 1000)

# Conditional branch logging
logger.debug("debug_h3_branch",
    condition="user.is_admin",
    value=user.is_admin,
    branch_taken="admin" if user.is_admin else "regular")

# Async operation tracking
logger.debug("debug_h4_async_start",
    operation="fetch_user_data",
    request_id=request_id,
    timestamp=time.time())

data = await fetch_user_data(user_id)

logger.debug("debug_h4_async_complete",
    operation="fetch_user_data",
    request_id=request_id,
    data_received=bool(data),
    elapsed_ms=(time.time() - start) * 1000)
```

### Using standard logging

```python
import logging

logger = logging.getLogger(__name__)

# Basic check
logger.debug("[DEBUG H1] user_id=%s expected=non-null", user_id)

# With dict for structured data
logger.debug("[DEBUG H2] %s", {
    "hypothesis": "cache_miss",
    "cache_key": key,
    "cache_hit": key in cache,
    "cached_value": cache.get(key)
})

# Exception context
try:
    result = risky_operation()
except Exception as e:
    logger.debug("[DEBUG H3] exception caught: %s, type=%s, args=%s",
        str(e), type(e).__name__, e.args)
    raise
```

### Database query logging

```python
# Before query
logger.debug("debug_h5_query",
    query_type="select",
    table="users",
    filters={"status": "active", "role": role},
    expected_count="1+")

# After query
results = session.execute(query).fetchall()

logger.debug("debug_h5_query_result",
    actual_count=len(results),
    first_result=results[0] if results else None,
    query_time_ms=elapsed)
```

## TypeScript/JavaScript Patterns

### Console logging (Browser/Node)

```typescript
// Basic hypothesis check
console.log('[DEBUG H1]', {
  hypothesis: 'state not updating',
  currentState: state,
  expectedState: 'updated value',
  timestamp: Date.now()
});

// React state debugging
console.log('[DEBUG H2] before setState', { 
  stateBefore: data,
  newValue: response 
});
setData(response);
// Use setTimeout to log after state update
setTimeout(() => {
  console.log('[DEBUG H2] after setState', { stateAfter: data });
}, 0);

// Event handler debugging
const handleClick = (e: React.MouseEvent) => {
  console.log('[DEBUG H3] click handler', {
    target: e.target,
    currentTarget: e.currentTarget,
    eventType: e.type,
    timestamp: Date.now()
  });
  // ... handler logic
};

// Async operation tracking
console.log('[DEBUG H4] fetch start', { url, requestId });
const startTime = performance.now();

try {
  const response = await fetch(url);
  const data = await response.json();
  
  console.log('[DEBUG H4] fetch complete', {
    requestId,
    status: response.status,
    dataReceived: !!data,
    elapsed: performance.now() - startTime
  });
} catch (error) {
  console.log('[DEBUG H4] fetch error', {
    requestId,
    error: error.message,
    elapsed: performance.now() - startTime
  });
}
```

### React-specific patterns

```typescript
// useEffect debugging
useEffect(() => {
  console.log('[DEBUG H5] useEffect triggered', {
    dependency1: dep1,
    dependency2: dep2,
    renderCount: renderCountRef.current
  });
  
  return () => {
    console.log('[DEBUG H5] useEffect cleanup', {
      dependency1: dep1,
      dependency2: dep2
    });
  };
}, [dep1, dep2]);

// Render debugging
console.log('[DEBUG H6] render', {
  props: { ...props },
  state: { data, loading, error },
  timestamp: Date.now()
});

// Context debugging
const contextValue = useContext(MyContext);
console.log('[DEBUG H7] context value', {
  contextValue,
  expectedKeys: ['user', 'settings'],
  actualKeys: Object.keys(contextValue || {})
});

// Ref debugging
console.log('[DEBUG H8] ref check', {
  refCurrent: ref.current,
  isNull: ref.current === null,
  elementType: ref.current?.tagName
});
```

### API/Network debugging

```typescript
// Request interceptor pattern
const debugFetch = async (url: string, options?: RequestInit) => {
  const requestId = crypto.randomUUID();
  
  console.log('[DEBUG H9] request', {
    requestId,
    url,
    method: options?.method || 'GET',
    headers: options?.headers,
    body: options?.body ? JSON.parse(options.body as string) : undefined
  });
  
  const start = performance.now();
  const response = await fetch(url, options);
  const elapsed = performance.now() - start;
  
  console.log('[DEBUG H9] response', {
    requestId,
    status: response.status,
    statusText: response.statusText,
    elapsed,
    headers: Object.fromEntries(response.headers.entries())
  });
  
  return response;
};
```

## Common Patterns (Any Language)

### Entry/Exit Pattern

Log at function boundaries to track execution flow:

```
[DEBUG H1] ENTRY function_name args={...}
[DEBUG H1] EXIT function_name result={...} elapsed=Xms
```

### Before/After Pattern

Log state before and after a mutation:

```
[DEBUG H2] BEFORE operation state={...}
[DEBUG H2] AFTER operation state={...} changed=true/false
```

### Branch Pattern

Log which code path is taken:

```
[DEBUG H3] BRANCH condition=X value=Y path_taken=Z
```

### Async Boundary Pattern

Log at async operation start and completion:

```
[DEBUG H4] ASYNC_START operation=X request_id=Y
[DEBUG H4] ASYNC_COMPLETE operation=X request_id=Y elapsed=Zms
```

### Error Context Pattern

Log full context when catching errors:

```
[DEBUG H5] ERROR_CAUGHT type=X message=Y context={...}
```

## Cleanup Checklist

After bug is fixed and verified, remove all debug logging:

```bash
# Find all debug logs (Python)
rg "debug_h\d|DEBUG H\d" backend/ --type py

# Find all debug logs (TypeScript)
rg "\[DEBUG H\d\]" frontend/ --type ts --type tsx

# Find structlog debug calls
rg 'logger\.debug\("debug_' backend/
```

Verify removal:
- [ ] No `[DEBUG H#]` patterns remain
- [ ] No `debug_h#` structlog events remain
- [ ] Tests still pass after removal
- [ ] No console.log statements left in production code
