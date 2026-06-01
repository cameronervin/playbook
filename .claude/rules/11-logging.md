# Logging Rules

## DO
- Use `structlog` for structured logging (JSON in prod, pretty in dev)
- Use appropriate log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Include context: request_id, user_id, operation name
- Log at service boundaries (entry/exit of major operations)
- Log errors with full stack traces
- Use lazy string formatting: `logger.info("processing", item_id=item_id)`

## DON'T
- Log passwords, tokens, API keys, or PII
- Use print() statements (use logger instead)
- Log inside tight loops (performance impact)
- Log raw request/response bodies (may contain sensitive data)
- Use string concatenation: `logger.info(f"User {user_id}")` ❌
- Log at DEBUG level in production hot paths

## Log Levels
| Level | Use For |
|-------|---------|
| DEBUG | Development troubleshooting, detailed state |
| INFO | Normal operations, business events |
| WARNING | Recoverable issues, deprecations |
| ERROR | Failures requiring attention |
| CRITICAL | System-wide failures, service down |

## Structured Logging Pattern
```python
import structlog

logger = structlog.get_logger(__name__)

# Good - structured with context
logger.info("item_created", item_id=item.id, user_id=user.id)
logger.error("payment_failed", order_id=order.id, error=str(e), exc_info=True)

# Bad - unstructured
logger.info(f"Created item {item.id} for user {user.id}")
```

## Request Context
```python
# Bind request context early in middleware
structlog.contextvars.bind_contextvars(
    request_id=request_id,
    user_id=current_user.id if current_user else None,
)
```

## What to Log
| Event | Level | Context |
|-------|-------|---------|
| Request received | INFO | method, path, request_id |
| Auth success/failure | INFO | user_id, method |
| Business operation | INFO | operation, entity_id |
| External API call | DEBUG | service, endpoint, duration_ms |
| Validation error | WARNING | field, value (sanitized) |
| Exception caught | ERROR | exc_info=True |
| Service startup/shutdown | INFO | version, environment |

## Security Reminders
- Sanitize user input before logging
- Never log: passwords, tokens, credit cards, SSN, API keys
- Mask sensitive fields: `email=mask_email(user.email)`
- Review logs for PII before enabling DEBUG in production
